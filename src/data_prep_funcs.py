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