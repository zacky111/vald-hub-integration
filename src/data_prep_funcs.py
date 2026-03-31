import pandas as pd

def prepare_tests_for_comparison(tests_details_all, selected_metrics):
    """
    Dla każdego testu:
    - zbiera metryki per trial
    - wybiera top 3 próby wg Jump Height (Flight Time)
    - liczy mean i std dla wybranych metryk
    Zwraca:
    - summary_df: 1 wiersz = 1 test, kolumny = metric_mean / metric_std
    - trials_data_per_test: dict z pełnymi danymi triali do dalszego użycia
    """
    jump_height_metric = "Jump Height (Flight Time)"

    def get_sort_date(test_obj):
        date_source = test_obj.get("recorded_date_utc") or test_obj.get("modified_date_utc")
        return pd.to_datetime(date_source, errors="coerce", utc=True)

    # Sortowanie chronologiczne, ale etykiety będą Test 1, Test 2, ...
    sorted_tests = sorted(
        tests_details_all,
        key=lambda x: (
            pd.isna(get_sort_date(x)),
            get_sort_date(x)
        )
    )

    summary_rows = []
    trials_data_per_test = {}

    for test_idx, test_obj in enumerate(sorted_tests):
        test_trials = test_obj["trials"]

        recorded_date_utc = test_obj.get("recorded_date_utc")
        modified_date_utc = test_obj.get("modified_date_utc")
        test_id = test_obj.get("test_id")
        test_type = test_obj.get("test_type")

        date_source = recorded_date_utc or modified_date_utc
        parsed_date = pd.to_datetime(date_source, errors="coerce", utc=True) if date_source else pd.NaT

        test_label = f"Test {parsed_date}"

        if not isinstance(test_trials, list) or not test_trials:
            continue

        comparison_data = {}

        for i, trial in enumerate(test_trials):
            trial_id = f"Trial {i + 1}"

            if "results" not in trial:
                continue

            for r in trial["results"]:
                metric_name = r["definition"]["name"]
                limb = r.get("limb")

                if limb == "Trial":
                    if metric_name not in comparison_data:
                        comparison_data[metric_name] = {}
                    comparison_data[metric_name][trial_id] = r["value"]

        if not comparison_data:
            continue

        comp_df = pd.DataFrame.from_dict(comparison_data, orient="index").transpose()

        if jump_height_metric not in comp_df.columns:
            continue

        trials_df = comp_df[comp_df.index.to_series().str.startswith("Trial")].copy()

        if trials_df.empty:
            continue

        trials_df[jump_height_metric] = pd.to_numeric(trials_df[jump_height_metric], errors="coerce")
        trials_df = trials_df.dropna(subset=[jump_height_metric])

        if trials_df.empty:
            continue

        top3_indices = trials_df[jump_height_metric].nlargest(3).index.tolist()
        best3_df = trials_df.loc[top3_indices].copy()

        metrics_to_use = [m for m in selected_metrics if m in best3_df.columns]

        # Jump Height zawsze ma być policzone
        if jump_height_metric in best3_df.columns:
            metrics_to_use = [jump_height_metric] + [m for m in metrics_to_use if m != jump_height_metric]

        if not metrics_to_use:
            continue

        for metric in metrics_to_use:
            best3_df[metric] = pd.to_numeric(best3_df[metric], errors="coerce")

        mean_series = best3_df[metrics_to_use].mean(numeric_only=True)
        std_series = best3_df[metrics_to_use].std(numeric_only=True)

        row = {
            "Test": test_label,
            "Test Order": test_idx + 1,
            "Test ID": test_id,
            "Test Type": test_type,
            "Recorded Date UTC": recorded_date_utc,
            "Modified Date UTC": modified_date_utc,
            "Plot Date": parsed_date,
            "Top 3 Trials": ", ".join(top3_indices),
            "Best Jump Height": trials_df.loc[top3_indices[0], jump_height_metric] if top3_indices else None,
        }

        for metric in metrics_to_use:
            row[f"{metric} Mean"] = mean_series.get(metric)
            row[f"{metric} Std"] = std_series.get(metric)

        summary_rows.append(row)

        trials_data_per_test[test_label] = {
            "test_id": test_id,
            "test_type": test_type,
            "recorded_date_utc": recorded_date_utc,
            "modified_date_utc": modified_date_utc,
            "all_trials_df": trials_df,
            "best3_df": best3_df,
            "top3_indices": top3_indices,
        }

    summary_df = pd.DataFrame(summary_rows)
    return summary_df, trials_data_per_test

def parse_excluded_tests(excluded_text, min_idx, max_idx):
    """
    Parsuje tekst z numerami testów do pominięcia.
    Obsługuje formaty:
    - "8"
    - "8,10,11"
    - "8 10 11"
    - "8;10;11"

    Zwraca:
    - sorted list[int] z numerami testów do pominięcia w dozwolonym zakresie
    """
    if not excluded_text or not str(excluded_text).strip():
        return []

    normalized = str(excluded_text)
    for sep in [",", ";", "\n", "\t"]:
        normalized = normalized.replace(sep, " ")

    excluded_numbers = []
    for part in normalized.split():
        try:
            number = int(part)
            if min_idx <= number <= max_idx:
                excluded_numbers.append(number)
        except ValueError:
            continue

    return sorted(set(excluded_numbers))

def group_metrics_by_base(metrics):
    """
    Grupuje metryki:
    - base -> { "Left": ..., "Right": ..., "Trial": ..., "Asym": ... }
    """
    grouped = {}

    for metric in metrics:
        if " - " in metric:
            base, limb = metric.rsplit(" - ", 1)
        else:
            base = metric
            limb = "Trial"

        grouped.setdefault(base, {})[limb] = metric

    return grouped

def normalize_metric_name(metric_name: str) -> str:
    if metric_name is None:
        return ""

    text = str(metric_name).strip().lower()

    replacements = {
        "assymetry": "asymmetry",
        "conctraction": "contraction",
        "body weight": "bodyweight",
        "body-weight": "bodyweight",
        "flight time": "flighttime",
        "jump height ft": "jumpheightflighttime",
        "rsi modified": "rsimodified",
    }
    for old, new in replacements.items():
        text = text.replace(old, new)

    text = re.sub(r"[^a-z0-9]+", "", text)
    return text


def split_metric_and_limb(metric_name: str, limb: str):
    """
    Zwraca:
    - base_metric_name: nazwa bazowa metryki
    - full_metric_name: nazwa metryki z suffixem limb, jeśli limb != Trial
    """
    base_metric_name = metric_name
    full_metric_name = metric_name if not limb or limb == "Trial" else f"{metric_name} - {limb}"
    return base_metric_name, full_metric_name


def extract_metric_record(result: dict):
    """
    Unified metric extractor from API result.
    Returns normalized metadata for easier matching/debugging.
    """
    definition = result.get("definition", {}) or {}
    metric_name = definition.get("name")
    metric_key = definition.get("result") or definition.get("id") or result.get("resultId")
    limb = result.get("limb", "Trial")
    value = result.get("value")

    if not metric_name:
        return None

    base_name, full_name = split_metric_and_limb(metric_name, limb)

    return {
        "metric_key": str(metric_key) if metric_key is not None else None,
        "metric_name": metric_name,
        "base_name": base_name,
        "full_name": full_name,
        "limb": limb,
        "value": value,
        "unit": definition.get("unit"),
        "description": definition.get("description"),
        "result_id": result.get("resultId"),
        "normalized_metric_key": normalize_metric_name(metric_key) if metric_key is not None else "",
        "normalized_name": normalize_metric_name(metric_name),
        "normalized_base": normalize_metric_name(base_name),
        "normalized_full": normalize_metric_name(full_name),
    }


def extract_available_metrics_from_tests(tests_details_all):
    """
    Zwraca listę wszystkich metryk dostępnych w pobranych testach.
    Każdy element:
    {
        "metric_key": ...,
        "metric_name": ...,
        "base_name": ...,
        "full_name": ...,
        "limb": ...,
        "normalized_metric_key": ...,
        "normalized_name": ...,
        "normalized_base": ...,
        "normalized_full": ...,
    }
    """
    available_entries = []
    seen = set()

    for test_obj in tests_details_all or []:
        trials = test_obj.get("trials", [])
        for trial in trials:
            for result in trial.get("results", []):
                record = extract_metric_record(result)
                if not record:
                    continue

                key = (
                    record["metric_key"],
                    record["base_name"],
                    record["full_name"],
                    record["limb"],
                )

                if key in seen:
                    continue

                seen.add(key)
                available_entries.append(record)

    return available_entries


def resolve_category_metrics_for_test_type(test_type, available_metric_entries):
    """
    Dopasowuje metryki z configu kategorii do realnych metryk z API.
    Matching jest bardziej ostrożny niż wcześniej:
    1. exact base match
    2. exact full match
    3. exact metric name match
    4. exact metric key match
    5. token / partial match

    Zwraca:
    - resolved: category -> lista pełnych nazw metryk z API
    - unmatched: category -> lista metryk z configu, których nie udało się dopasować
    """
    category_config = TEST_TYPE_METRIC_CATEGORIES.get(test_type, {})
    resolved = {}
    unmatched = {}

    for category, config_metrics in category_config.items():
        resolved[category] = []
        unmatched[category] = []

        for config_metric in config_metrics:
            normalized_config = normalize_metric_name(config_metric)
            matched_entries = []

            # 1. exact base match
            matched_entries = [
                entry["full_name"]
                for entry in available_metric_entries
                if entry["normalized_base"] == normalized_config
            ]

            # 2. exact full match
            if not matched_entries:
                matched_entries = [
                    entry["full_name"]
                    for entry in available_metric_entries
                    if entry["normalized_full"] == normalized_config
                ]

            # 3. exact metric name match
            if not matched_entries:
                matched_entries = [
                    entry["full_name"]
                    for entry in available_metric_entries
                    if entry["normalized_name"] == normalized_config
                ]

            # 4. exact metric key match
            if not matched_entries:
                matched_entries = [
                    entry["full_name"]
                    for entry in available_metric_entries
                    if entry["normalized_metric_key"] == normalized_config
                ]

            # 5. partial match - ostrożniejszy
            if not matched_entries:
                matched_entries = [
                    entry["full_name"]
                    for entry in available_metric_entries
                    if (
                        normalized_config in entry["normalized_base"]
                        or normalized_config in entry["normalized_name"]
                        or normalized_config in entry["normalized_full"]
                        or entry["normalized_base"] in normalized_config
                    )
                ]

            matched_entries = list(dict.fromkeys(matched_entries))

            if matched_entries:
                for metric in matched_entries:
                    if metric not in resolved[category]:
                        resolved[category].append(metric)
            else:
                unmatched[category].append(config_metric)

    return resolved, unmatched


def build_comparison_df_for_test_trials(test_trials):
    """
    Buduje dataframe trial x metric ze WSZYSTKIMI metrykami z API.
    NIE odcina żadnych kolumn.
    """
    comparison_data = {}

    for i, trial in enumerate(test_trials):
        trial_id = f"Trial {i + 1}"

        if "results" not in trial:
            continue

        for result in trial["results"]:
            record = extract_metric_record(result)
            if not record:
                continue

            full_metric_name = record["full_name"]
            value = record["value"]

            if full_metric_name not in comparison_data:
                comparison_data[full_metric_name] = {}

            comparison_data[full_metric_name][trial_id] = value

    if not comparison_data:
        return pd.DataFrame()

    comp_df = pd.DataFrame.from_dict(comparison_data, orient="index").transpose()
    return comp_df


def find_jump_height_column(df: pd.DataFrame):
    """
    Znajduje najlepszą kolumnę do sortowania top 3 prób.
    Preferowana:
    - Jump Height (Flight Time)
    Fallback:
    - Jump Height...
    """
    preferred = "Jump Height (Flight Time)"
    if preferred in df.columns:
        return preferred

    candidates = [c for c in df.columns if "Jump Height" in str(c)]
    if candidates:
        return candidates[0]

    return None


def prepare_tests_for_comparison(tests_details_all, selected_metrics=None, use_all_metrics=False):
    """
    Dla każdego testu:
    - zbiera WSZYSTKIE metryki per trial (Trial, Left, Right, Asym, itd.)
    - wybiera top 3 próby wg Jump Height (Flight Time) lub fallback Jump Height*
    - liczy mean i std dla:
        * selected_metrics, albo
        * wszystkich metryk jeśli use_all_metrics=True

    Zwraca:
    - summary_df
    - trials_data_per_test
    """
    selected_metrics = selected_metrics or []

    def get_sort_date(test_obj):
        date_source = test_obj.get("recorded_date_utc") or test_obj.get("modified_date_utc")
        return pd.to_datetime(date_source, errors="coerce", utc=True)

    sorted_tests = sorted(
        tests_details_all,
        key=lambda x: (
            pd.isna(get_sort_date(x)),
            get_sort_date(x)
        )
    )

    summary_rows = []
    trials_data_per_test = {}

    for test_idx, test_obj in enumerate(sorted_tests):
        test_trials = test_obj["trials"]

        recorded_date_utc = test_obj.get("recorded_date_utc")
        modified_date_utc = test_obj.get("modified_date_utc")
        test_id = test_obj.get("test_id")
        test_type = test_obj.get("test_type")

        date_source = recorded_date_utc or modified_date_utc
        parsed_date = pd.to_datetime(date_source, errors="coerce", utc=True) if date_source else pd.NaT

        test_label = f"Test {test_idx + 1}"

        if not isinstance(test_trials, list) or not test_trials:
            continue

        comp_df = build_comparison_df_for_test_trials(test_trials)

        if comp_df.empty:
            continue

        trials_df = comp_df[comp_df.index.to_series().str.startswith("Trial")].copy()
        if trials_df.empty:
            continue

        jump_height_metric = find_jump_height_column(trials_df)

        if jump_height_metric:
            trials_df[jump_height_metric] = pd.to_numeric(trials_df[jump_height_metric], errors="coerce")
            trials_df_for_sort = trials_df.dropna(subset=[jump_height_metric]).copy()
        else:
            trials_df_for_sort = trials_df.copy()

        if trials_df_for_sort.empty:
            continue

        if jump_height_metric:
            top3_indices = trials_df_for_sort[jump_height_metric].nlargest(min(3, len(trials_df_for_sort))).index.tolist()
        else:
            top3_indices = trials_df_for_sort.index[:min(3, len(trials_df_for_sort))].tolist()

        if not top3_indices:
            continue

        best3_df = trials_df.loc[top3_indices].copy()

        if use_all_metrics:
            metrics_to_use = list(best3_df.columns)
        else:
            metrics_to_use = [m for m in selected_metrics if m in best3_df.columns]

        if jump_height_metric and jump_height_metric in best3_df.columns and jump_height_metric not in metrics_to_use:
            metrics_to_use = [jump_height_metric] + metrics_to_use

        metrics_to_use = list(dict.fromkeys(metrics_to_use))

        if not metrics_to_use:
            continue

        for metric in metrics_to_use:
            best3_df[metric] = pd.to_numeric(best3_df[metric], errors="coerce")

        mean_series = best3_df[metrics_to_use].mean(numeric_only=True)
        std_series = best3_df[metrics_to_use].std(numeric_only=True)

        row = {
            "Test": test_label,
            "Test Order": test_idx + 1,
            "Test ID": test_id,
            "Test Type": test_type,
            "Recorded Date UTC": recorded_date_utc,
            "Modified Date UTC": modified_date_utc,
            "Plot Date": parsed_date,
            "Top 3 Trials": ", ".join(top3_indices),
            "Best Jump Height": trials_df.loc[top3_indices[0], jump_height_metric] if jump_height_metric and top3_indices else None,
            "Jump Height Metric Used": jump_height_metric if jump_height_metric else "None",
        }

        for metric in metrics_to_use:
            row[f"{metric} Mean"] = mean_series.get(metric)
            row[f"{metric} Std"] = std_series.get(metric)

        summary_rows.append(row)

        trials_data_per_test[test_label] = {
            "test_id": test_id,
            "test_type": test_type,
            "recorded_date_utc": recorded_date_utc,
            "modified_date_utc": modified_date_utc,
            "all_trials_df": trials_df,
            "best3_df": best3_df,
            "top3_indices": top3_indices,
            "jump_height_metric_used": jump_height_metric,
            "all_metric_columns": list(trials_df.columns),
        }

    summary_df = pd.DataFrame(summary_rows)
    return summary_df, trials_data_per_test


def get_all_trial_metric_names(specific_test_details):
    """
    Returns all Trial-level metric names from single-test details.
    """
    metric_names = set()

    if not isinstance(specific_test_details, list):
        return []

    for trial in specific_test_details:
        for result in trial.get("results", []):
            record = extract_metric_record(result)
            if not record:
                continue
            if record["limb"] == "Trial":
                metric_names.add(record["metric_name"])

    return sorted(metric_names)