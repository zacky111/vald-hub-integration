import pandas as pd
import numpy as np
import re

from src.metric_categories import TEST_TYPE_METRIC_CATEGORIES

def prepare_tests_for_comparison(tests_details_all, selected_metrics=None, use_all_metrics=False):
    """
    Dla każdego testu:
    - zbiera WSZYSTKIE metryki per trial (Trial, Left, Right, Asym, itd.)
    - wybiera top 3 próby wg Jump Height
    - wybiera top 1 próbę wg Jump Height
    - liczy mean/std z top 3
    - zapisuje wartość Top1 dla każdej metryki

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
            top3_indices = trials_df_for_sort[jump_height_metric].nlargest(
                min(3, len(trials_df_for_sort))
            ).index.tolist()

            top1_index = trials_df_for_sort[jump_height_metric].nlargest(1).index.tolist()
        else:
            top3_indices = trials_df_for_sort.index[:min(3, len(trials_df_for_sort))].tolist()
            top1_index = trials_df_for_sort.index[:1].tolist()

        if not top3_indices:
            continue

        best3_df = trials_df.loc[top3_indices].copy()
        best1_df = trials_df.loc[top1_index].copy() if top1_index else pd.DataFrame()

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

            if not best1_df.empty and metric in best1_df.columns:
                best1_df[metric] = pd.to_numeric(best1_df[metric], errors="coerce")

        mean_series = best3_df[metrics_to_use].mean(numeric_only=True)
        std_series = best3_df[metrics_to_use].std(numeric_only=True)

        if not best1_df.empty:
            top1_series = best1_df[metrics_to_use].mean(numeric_only=True)
        else:
            top1_series = pd.Series(dtype="float64")

        row = {
            "Test": test_label,
            "Test Order": test_idx + 1,
            "Test ID": test_id,
            "Test Type": test_type,
            "Recorded Date UTC": recorded_date_utc,
            "Modified Date UTC": modified_date_utc,
            "Plot Date": parsed_date,
            "Top 3 Trials": ", ".join(top3_indices),
            "Best 1 Trial": top1_index[0] if top1_index else None,
            "Best Jump Height": trials_df.loc[top3_indices[0], jump_height_metric] if jump_height_metric and top3_indices else None,
            "Jump Height Metric Used": jump_height_metric if jump_height_metric else "None",
        }

        for metric in metrics_to_use:
            row[f"{metric} Mean"] = mean_series.get(metric)
            row[f"{metric} Std"] = std_series.get(metric)
            row[f"{metric} Top1"] = top1_series.get(metric)

        summary_rows.append(row)

        trials_data_per_test[test_label] = {
            "test_id": test_id,
            "test_type": test_type,
            "recorded_date_utc": recorded_date_utc,
            "modified_date_utc": modified_date_utc,
            "all_trials_df": trials_df,
            "best3_df": best3_df,
            "top3_indices": top3_indices,
            "best1_df": best1_df,
            "top1_index": top1_index[0] if top1_index else None,
            "jump_height_metric_used": jump_height_metric,
            "all_metric_columns": list(trials_df.columns),
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


def parse_forcedeck_raw_data(raw_data: dict) -> pd.DataFrame:
    """
    Parsuje raw data z ForceDecks i zwraca DataFrame z kolumnami:
    - time
    - left
    - right
    - total

    Oczekiwany format:
    {
        "recordingDataHeader": ["Time", "Z Left", "Z Right"],
        "recordingData": [
            [0, -1.15, -2.17],
            [0.001, -1.15, 1.82],
            ...
        ]
    }
    """
    if not raw_data:
        raise ValueError("raw_data is empty")

    headers = raw_data.get("recordingDataHeader")
    rows = raw_data.get("recordingData")

    if not headers or not rows:
        raise ValueError("Missing recordingDataHeader or recordingData")

    df = pd.DataFrame(rows, columns=headers)

    # Szukanie kolumn niezależnie od wielkości liter
    col_map = {col.strip().lower(): col for col in df.columns}

    time_col = col_map.get("time")
    left_col = col_map.get("z left")
    right_col = col_map.get("z right")

    if time_col is None:
        raise ValueError("Column 'Time' not found in recordingDataHeader")
    if left_col is None:
        raise ValueError("Column 'Z Left' not found in recordingDataHeader")
    if right_col is None:
        raise ValueError("Column 'Z Right' not found in recordingDataHeader")

    parsed_df = pd.DataFrame({
        "time": pd.to_numeric(df[time_col], errors="coerce"),
        "left": pd.to_numeric(df[left_col], errors="coerce"),
        "right": pd.to_numeric(df[right_col], errors="coerce"),
    })

    parsed_df["total"] = parsed_df["left"] + parsed_df["right"]
    parsed_df = parsed_df.dropna(subset=["time", "left", "right"]).reset_index(drop=True)

    return parsed_df


def estimate_bodyweight(total_force: pd.Series) -> float:
    positive = total_force[total_force > 50]
    if len(positive) == 0:
        raise ValueError("Cannot estimate bodyweight from signal")

    cutoff = positive.quantile(0.7)
    bw_candidates = positive[positive >= cutoff]

    if len(bw_candidates) == 0:
        bw_candidates = positive

    return float(bw_candidates.median())


def detect_takeoff_events(
    df: pd.DataFrame,
    sampling_frequency: int = 1000,
    min_flight_ms: int = 80,
    force_threshold_ratio: float = 0.05,
    min_separation_ms: int = 300,
    min_contact_before_takeoff_ms: int = 200,
    contact_threshold_ratio: float = 0.5
):
    """
    Wykrywa take-off tylko wtedy, gdy przed fazą lotu był wyraźny kontakt z platformą.
    """
    total = df["total"].to_numpy()
    bw = estimate_bodyweight(df["total"])

    flight_threshold = bw * force_threshold_ratio
    contact_threshold = bw * contact_threshold_ratio

    min_flight_samples = int((min_flight_ms / 1000) * sampling_frequency)
    min_separation_samples = int((min_separation_ms / 1000) * sampling_frequency)
    min_contact_samples = int((min_contact_before_takeoff_ms / 1000) * sampling_frequency)

    below = total < flight_threshold
    above_contact = total > contact_threshold

    takeoff_indices = []
    i = 0
    n = len(total)

    while i < n - min_flight_samples:
        if below[i]:
            j = i
            while j < n and below[j]:
                j += 1

            flight_len = j - i

            if flight_len >= min_flight_samples:
                contact_start = max(0, i - min_contact_samples)
                had_contact_before = (
                    above_contact[contact_start:i].sum() >= int(0.7 * (i - contact_start))
                    if i > contact_start else False
                )

                if had_contact_before:
                    takeoff_indices.append(i)
                    i = j + min_separation_samples
                    continue

            i = j
        else:
            i += 1

    return takeoff_indices, bw

def find_movement_onset_before_takeoff(
    df: pd.DataFrame,
    takeoff_idx: int,
    sampling_frequency: int = 1000,
    search_back_ms: int = 1500,
    baseline_ms: int = 300,
    min_onset_duration_ms: int = 30,
    std_multiplier: float = 5.0,
    min_absolute_change_n: float = 20.0
):
    """
    Szuka movement onset (punkt 1) w oknie poprzedzającym take-off.
    Onset = pierwsze trwałe odejście od lokalnego baseline'u, ale
    szukane tylko w obrębie konkretnej próby przed wybiciem.
    """
    total = df["total"].to_numpy()
    n = len(total)

    search_back_samples = int((search_back_ms / 1000) * sampling_frequency)
    baseline_samples = int((baseline_ms / 1000) * sampling_frequency)
    min_onset_samples = int((min_onset_duration_ms / 1000) * sampling_frequency)

    search_start = max(0, takeoff_idx - search_back_samples)
    search_end = takeoff_idx

    if search_end - search_start < baseline_samples + min_onset_samples:
        return max(0, takeoff_idx - baseline_samples)

    # Szukamy onset od początku okna do take-off
    for i in range(search_start + baseline_samples, search_end - min_onset_samples):
        baseline = total[i - baseline_samples:i]
        bw = float(np.mean(baseline))
        sd = float(np.std(baseline))
        threshold = max(std_multiplier * sd, min_absolute_change_n)

        window = total[i:i + min_onset_samples]
        deviation = np.abs(window - bw) > threshold

        if deviation.all():
            return i

    # fallback: jeśli nic nie znajdziemy, zwróć trochę wcześniej niż take-off
    return max(search_start, takeoff_idx - int(0.6 * sampling_frequency))

def extract_trial_aligned_to_takeoff(
    df: pd.DataFrame,
    takeoff_idx: int,
    pre_ms: int = 200,
    post_ms: int = 2000,
    sampling_frequency: int = 1000
) -> pd.DataFrame:
    """
    Wycina fragment wokół wskazanego eventu i ustawia czas względny.
    Nazwa zachowana dla zgodności z istniejącym kodem.
    """
    pre_samples = int((pre_ms / 1000) * sampling_frequency)
    post_samples = int((post_ms / 1000) * sampling_frequency)

    start_idx = max(0, takeoff_idx - pre_samples)
    end_idx = min(len(df), takeoff_idx + post_samples)

    trial_df = df.iloc[start_idx:end_idx].copy().reset_index(drop=True)

    event_time = df.iloc[takeoff_idx]["time"]
    trial_df["time_rel"] = trial_df["time"] - event_time

    return trial_df

def prepare_overlay_trial(
    raw_data: dict,
    leg: str = "Both",
    trial_number: int = 1,
    pre_ms: int = 200,
    post_ms: int = 2000
):
    df = parse_forcedeck_raw_data(raw_data)
    sampling_frequency = int(raw_data.get("samplingFrequency", 1000))

    takeoff_indices, bw = detect_takeoff_events(
        df,
        sampling_frequency=sampling_frequency
    )

    if not takeoff_indices:
        raise ValueError("No valid trials detected in this recording")

    if trial_number < 1 or trial_number > len(takeoff_indices):
        raise ValueError(f"trial_number must be between 1 and {len(takeoff_indices)}")

    takeoff_idx = takeoff_indices[trial_number - 1]

    onset_idx = find_movement_onset_before_takeoff(
        df,
        takeoff_idx=takeoff_idx,
        sampling_frequency=sampling_frequency,
        search_back_ms=1500,
        baseline_ms=300,
        min_onset_duration_ms=30,
        std_multiplier=5.0,
        min_absolute_change_n=20.0
    )

    trial_df = extract_trial_aligned_to_takeoff(
        df,
        takeoff_idx=onset_idx,
        pre_ms=pre_ms,
        post_ms=post_ms,
        sampling_frequency=sampling_frequency
    )

    pre_onset = trial_df[trial_df["time_rel"] < 0]
    post_onset = trial_df[trial_df["time_rel"] >= 0]

    if pre_onset.empty:
        raise ValueError("Detected trial has no pre-onset baseline")

    if post_onset.empty:
        raise ValueError("Detected trial has no post-onset data")

    # sanity check: po onset powinien istnieć realny ruch
    if float(post_onset["total"].max()) < bw * 0.7:
        raise ValueError("Detected event does not look like a valid movement trial")

    if leg == "Left":
        plot_cols = ["left"]
    elif leg == "Right":
        plot_cols = ["right"]
    else:
        plot_cols = ["left", "right", "total"]

    return trial_df, plot_cols, len(takeoff_indices), bw




def detect_movement_onset_events(
    df: pd.DataFrame,
    sampling_frequency: int = 1000,
    baseline_window_ms: int = 500,
    min_onset_duration_ms: int = 30,
    std_multiplier: float = 5.0,
    min_absolute_change_n: float = 20.0,
    min_separation_ms: int = 1000
):
    """
    Wykrywa początki ruchu (movement onset, punkt 1) jako pierwsze trwałe
    odejście siły całkowitej od lokalnego poziomu spoczynkowego.

    Zwraca:
    - listę indeksów onsetów
    - medianę oszacowanego bodyweight z kolejnych baseline'ów
    """
    total = df["total"].to_numpy()
    n = len(total)

    baseline_samples = int((baseline_window_ms / 1000) * sampling_frequency)
    min_onset_samples = int((min_onset_duration_ms / 1000) * sampling_frequency)
    min_separation_samples = int((min_separation_ms / 1000) * sampling_frequency)

    if n < baseline_samples + min_onset_samples:
        raise ValueError("Signal too short to detect movement onset")

    onset_indices = []
    bw_estimates = []

    i = baseline_samples
    while i < n - min_onset_samples:
        baseline_start = max(0, i - baseline_samples)
        baseline_end = i

        baseline = total[baseline_start:baseline_end]
        if len(baseline) < baseline_samples // 2:
            i += 1
            continue

        bw = float(np.mean(baseline))
        sd = float(np.std(baseline))

        threshold = max(std_multiplier * sd, min_absolute_change_n)

        window = total[i:i + min_onset_samples]
        deviation = np.abs(window - bw) > threshold

        if deviation.all():
            onset_indices.append(i)
            bw_estimates.append(bw)
            i += min_separation_samples
        else:
            i += 1

    if not onset_indices:
        raise ValueError("No movement onset events detected")

    bw_final = float(np.median(bw_estimates)) if bw_estimates else estimate_bodyweight(df["total"])

    return onset_indices, bw_final