from datetime import datetime
import fnmatch
import io
from logging import warn
from pathlib import Path
import re
import warnings
import numpy as np
import pandas as pd
from tqdm import tqdm
from agentlab.analyze.error_categorization import (
    ERR_CLASS_MAP,
    is_critical_server_error,
    is_minor_server_error,
)
from browsergym.experiments.loop import ExpResult, yield_all_exp_results, get_exp_result
from agentlab.experiments.exp_utils import RESULTS_DIR

from IPython.display import display
from agentlab.utils.bootstrap import bootstrap_matrix, convert_df_to_array
from agentlab.experiments.task_collections import TASK_CATEGORY_MAP

warnings.filterwarnings("ignore", category=pd.errors.PerformanceWarning)

try:
    import pyperclip
except ImportError:
    pyperclip = None

pd.set_option("display.multi_sparse", False)


def get_constants_and_variables(df: pd.DataFrame, drop_constants: bool = False):
    """Filter out constants from the dataframe."""

    constants = {}
    variable_keys = []
    for col in df.columns:
        if df[col].nunique(dropna=False) == 1:
            if isinstance(df[col].iloc[0], np.generic):
                val = df[col].iloc[0].item()
            else:
                val = df[col].iloc[0]
            constants[col] = val
            if drop_constants:
                df = df.drop(col, axis=1)
        else:
            variable_keys.append(col)

    return constants, variable_keys, df


def set_index_from_variables(
    df: pd.DataFrame,
    index_white_list=("agent_args.*",),
    index_black_list=("*model_url*",),
    task_key="env_args.task_name",
    force_at_leaste_one_variable=False,
):
    """Set the index, inplace, to env_args.task_name and all variables.

    Introspects `df` to find all fields that are variable and set the index to
    those fields. This will allow to easily groupby and compare results. To
    filter undersired variables from the index, use index_white_list and
    index_black_list.

    Args:
        df: The dataframe to modify
        index_white_list: List of wildard patterns to match variables that
            should be included in the index.
        index_black_list: List of wildard patterns to match variables that
            should be excluded from the index.
    """
    df.reset_index(inplace=True)
    constants, variables, _ = get_constants_and_variables(df)

    index_variables = []
    for var in variables:
        white = any([fnmatch.fnmatch(var, pattern) for pattern in index_white_list])
        black = any([fnmatch.fnmatch(var, pattern) for pattern in index_black_list])

        if white and not black:
            index_variables.append(var)

    for var in index_variables:
        if df[var].isnull().any():
            warn(
                f"Variable {var} contains NaN or None values. This will be replaced by the string 'None' to avoid some pandas bug."
            )
            df[var] = df[var].fillna("None")

    if len(index_variables) == 0 and force_at_leaste_one_variable:
        if "agent_args.agent_name" in constants:
            index_variables = ["agent_args.agent_name"]

    # agent_variables = [var for var in variables if var.startswith("agent_args.")]
    df.set_index([task_key] + index_variables, inplace=True)
    df.sort_index(inplace=True)


def load_result_df(
    exp_dir,
    progress_fn=tqdm,
    set_index=True,
    result_df=None,
    index_white_list=("agent_args.*",),
    index_black_list=("*model_url*",),
):
    """Load the result dataframe.

    Will set the index to env_args.task_name and all columens that are not constant and
    starts with agent_args. This will allow to easily groupby and compare
    results. This index can be changed later using df.set_index.

    Args:
        exp_dir: Path to the experiment directory
        progress_fn: Progress function to use when loading the results
        set_index: If True, set the index to env_args.task_name and variable agent_args
        result_df: If not None, speed up the loading process by reusing
            alreading loaded objects.
        index_white_list: List of wildard patterns to match variables that
            should be included in the index.
        index_black_list: List of wildard patterns to match variables that
            should be excluded from the index.
    """

    if result_df is not None:
        result_list = list(result_df["exp_result"])
    else:
        result_list = list(yield_all_exp_results(exp_dir, progress_fn=progress_fn))

    if len(result_list) == 0:
        return None

    if progress_fn is not None:
        result_list = progress_fn(result_list, desc="Loading results")

    df = pd.DataFrame([exp_result.get_exp_record() for exp_result in result_list])
    if set_index:
        set_index_from_variables(df, index_white_list, index_black_list)
    return df


def reduce_episodes(result_df: pd.DataFrame):
    """Reduce the dataframe to a single row per episode and summarize some of
    the columns.
    """

    levels = list(range(result_df.index.nlevels))
    return result_df.groupby(level=levels).apply(summarize)


def report_2d(df: pd.DataFrame, reduce_fn: callable = reduce_episodes, n_row_keys=1):
    """Generic function to create a 2d report based on the dataframe.

    The code is simple but can be a bit cryptic. This is best explained in the
    following  3 steps:
    1) Groupby: Will use the existing multi-index to groupby. Make sure to set the
       an index to the desired keys before calling this function.
    2) Reduce: Uses the reduce_fn to reduce the content of each group to a single
       variable, creating a 1D series indexed by its original index.
    3) Unstack: Produce a 2D table such that the first n_row_keys are used to
       specify how many dimensions are used for the rows. The remaining
       dimensions are used for the columns.
    """

    levels = list(range(df.index.nlevels))
    reduced_df = df.groupby(level=levels).apply(reduce_fn)  # type: pd.Series
    return reduced_df.unstack(level=levels[n_row_keys:])


def report_constant_and_variables(df, show_stack_traces=True):
    constants, variables, _ = get_constants_and_variables(df)
    print("Constants:")
    for k, v in constants.items():
        print(f"    {k}: {v}")

    print("\nVariables:")
    for var in variables:
        if not show_stack_traces and var == "stack_trace":
            continue

        # get unique with count and sort by count descending
        unique_counts = df[var].value_counts().sort_values(ascending=False)

        print(f"    {var}: n_unique={len(unique_counts)}")
        for i, (val, count) in enumerate(unique_counts.items()):
            print(f"        {count}x : {val}")
            if i >= 2:
                break
        if len(unique_counts) > 3:
            print(f"        ...\n")


def get_bootstrap(
    df, metric, reduce_fn=np.nanmean, n_bootstrap=100, group_by="env_args.task_name", prior=0.5
):
    """Get the stratified bootstrap mean and std for the given metric."""
    grouped_df = df.reset_index(inplace=False).groupby(group_by)
    array = convert_df_to_array(grouped_df, metric=metric, threshold=0.7)
    if prior is not None:
        prior = prior * np.ones((len(array), 1))
        array = np.concatenate([array, prior], axis=1)

    bootstrapped_values = bootstrap_matrix(array, n_bootstrap=n_bootstrap, reduce_fn=reduce_fn)
    return np.nanmean(bootstrapped_values), np.nanstd(bootstrapped_values)


def summarize(sub_df):
    if not "cum_reward" in sub_df:
        record = dict(
            avg_reward=np.nan,
            uncertainty_reward=np.nan,
            avg_raw_reward=np.nan,
            avg_steps=np.nan,
            n_completed=f"0/{len(sub_df)}",
            n_err=0,
        )
    else:
        err = sub_df["err_msg"].notnull()
        n_completed = (err | sub_df["truncated"] | sub_df["terminated"]).sum()

        if n_completed == 0:
            return None
        _mean_reward, std_reward = get_bootstrap(sub_df, "cum_reward")

        # sanity check, if there is an error the reward should be zero
        assert sub_df[sub_df["err_msg"].notnull()]["cum_reward"].sum() == 0

        record = dict(
            avg_reward=sub_df["cum_reward"].mean(skipna=True).round(3),
            uncertainty_reward=std_reward.round(3),
            avg_raw_reward=sub_df["cum_raw_reward"].mean(skipna=True).round(3),
            avg_steps=sub_df["n_steps"].mean(skipna=True).round(3),
            n_completed=f"{n_completed}/{len(sub_df)}",
            n_err=err.sum(skipna=True),
        )

    return pd.Series(record)


def summarize_stats(sub_df):
    """Summarize the stats columns."""

    # make sure there are completed runs
    err = sub_df["err_msg"].notnull()
    n_completed = (err | sub_df["truncated"] | sub_df["terminated"]).sum()
    if n_completed == 0:
        return None

    record = dict(
        avg_reward=sub_df["cum_reward"].mean(skipna=True).round(3),
    )
    for key in sub_df.keys():
        if key.startswith("stats."):
            key_ = key.split(".")[1]
            op = key_.split("_")[0]
            if op == "cum":
                record[key_] = sub_df[key].sum(skipna=True).round(3)
            elif op == "max":
                record[key_] = sub_df[key].max(skipna=True).round(3)
            else:
                raise ValueError(f"Unknown stats operation: {op}")
    return pd.Series(record)


# NOTE: decprecated but I might want to use it again
def summarize_tgi(sub_df):
    err = sub_df["err_msg"].notnull()

    n_server_errors = (
        sub_df["stack_trace"]
        .apply(
            is_server_error,
        )
        .sum()
    )

    n_completed = (err | sub_df["truncated"] | sub_df["terminated"]).sum()

    record = dict(
        avg_reward=sub_df["cum_reward"].mean(skipna=True).round(3),
        avg_reward_server_corr=(
            sub_df["cum_reward"].mean(skipna=True) * n_completed / (n_completed - n_server_errors)
        ).round(3),
        avg_raw_reward=sub_df["cum_raw_reward"].mean(skipna=True).round(3),
        avg_steps=sub_df["n_steps"].mean(skipna=True).round(3),
        n_completed=f"{n_completed}/{len(sub_df)}",
        n_err=err.sum(skipna=True),
        n_server_errors=n_server_errors,
        # total_cost=sub_df["total_cost"].sum(skipna=True).round(3),
        # exp_dir=",".join([str(path).split("/")[-1] for path in sub_df["exp_dir"]]),
    )

    return pd.Series(record)


def _find_diff(tuple1, tuple2):
    """return the list of index wher tuple1 != tuple2"""
    return [i for i, (a, b) in enumerate(zip(tuple1, tuple2)) if a != b]


def _extract_ablation_study(report: pd.DataFrame, progression=False):
    """Reduce the multi-index to a change description compared to the previous row."""
    names = report.index.names
    report = report.copy()
    # report.sort_index(inplace=True)

    reference_index = None
    for index in report.index:
        if reference_index is not None:
            diffs = _find_diff(reference_index, index)
            change = "↳ " + ", ".join([f"{names[i]}={index[i]}" for i in diffs])
        else:
            change = "Initial Configuration"
        report.loc[index, "change"] = change
        if progression:
            reference_index = index
        else:
            reference_index = report.index[0]

    report = report.reset_index()
    report = report.set_index(["change"])

    # delete columns related to old index
    return report.drop(names, axis=1)


def ablation_report(result_df: pd.DataFrame, reduce_fn=summarize, progression=False):
    """Reduce the multi-index to a change description compared to the previous row.

    *NOTE*: This assumes that this experiments was launched with make_ablation_study.

    Rows will be sorted according to the average ExpArgs.order for all
    experiments associated with the multi-index.

    Args:
        result_df: The result dataframe as returned by load_result_df.
        reduce_fn: The function to use to reduce the sub dataframe. By default
            this is summarize.
    Returns:
        A dataframe with the change description as index.
    """
    report = global_report(result_df, reduce_fn=reduce_fn)
    report = _sort_order(result_df, report)
    report = _extract_ablation_study(report, progression=progression)
    return report


def _get_avg_order(df: pd.DataFrame, row: pd.Series):
    """Return the average order for the given row."""
    df = df.reset_index(level=0, drop=True, inplace=False)
    # df.sort_index(inplace=True)

    sub_df = df.loc[row.name]
    orders = [get_exp_result(exp_dir).exp_args.order for exp_dir in sub_df.exp_dir]
    orders = [order for order in orders if order is not None]
    if len(orders) == 0:
        return None
    return np.mean(orders)


def _sort_order(result_df, report):
    """Add a column to the report with the average order for each agent and sort."""

    def add_order(row):
        return _get_avg_order(result_df, row)

    report["avg_order"] = report.apply(add_order, axis=1)
    return report.sort_values("avg_order", ascending=True)


def global_report(
    result_df: pd.DataFrame,
    reduce_fn=summarize,
    rename_index=lambda name: name.replace("agent_args.flags.", ""),
):
    """Produce a report that summarize all tasks and all episodes for each
    agent.

    Parameters
    ----------
    result_df : pd.DataFrame
        The result dataframe as returned by load_result_df.
    reduce_fn : callable to summarize sub dataframe
    rename_index : callable, optional
        Function to rename the index. By default we remove the prefix
        "agent_args.flags."
    apply_shrink_columns: Make the column more compat
    """

    levels = list(range(result_df.index.nlevels))

    if len(levels) == 1:
        print("Only one configuration is found, returning a per-task report.")
        report = report_2d(result_df, reduce_fn=reduce_fn)
        report.loc["[ALL TASKS]"] = reduce_fn(result_df)
    else:
        print(
            "Found multiple configuration, averaging across tasks and returning a per-agent report."
        )
        report = result_df.groupby(level=levels[1:]).apply(reduce_fn)

        if rename_index is not None:
            index_names = [rename_index(name) for name in report.index.names]
            report = report.rename_axis(index=index_names)

        # if has key avg_reward
        if "avg_reward" in report.columns:
            report = report.sort_values("avg_reward", ascending=False)

    return report


def _rename_bool_flags(report: pd.DataFrame, true_str="✓", false_str="-"):
    """Rename the boolean flags to be more compact and readable."""
    map_bool = lambda x: true_str if x is True else false_str if x is False else x
    if isinstance(report.index, pd.MultiIndex):
        report.index = report.index.set_levels(
            [[map_bool(i) for i in level] for level in report.index.levels]
        )
    return report


def to_clipboard(df: pd.DataFrame):
    """Copy the dataframe to the clipboard as a tab separated csv."""
    output = io.StringIO()
    df.to_csv(output, sep="\t", index=True)
    csv_string = output.getvalue()
    if pyperclip is not None:
        try:
            pyperclip.copy(csv_string)
        except Exception as e:
            warn(f"Failed to copy to clipboard: {e}")
    else:
        print("pyperclip is not installed, cannot copy to clipboard.")
    return df


def flag_report(report: pd.DataFrame, metric: str = "avg_reward", round_digits: int = 2):
    # for all index in the multi-index with boolean value, get the average for
    # True and the average for False separately. Produce a new dataframe with
    # the average for True and False for each index and the ratio between the
    # two as a new column.

    # check the number of levels
    if report.index.nlevels <= 1:
        print(f"Only {report.index.nlevels} levels in the index, cannot produce flag report.")
        return

    report = report.copy()
    report = report.reset_index()

    records = []
    for col in report.columns:
        if report[col].dtype == bool:
            avg_true = report[report[col]][metric].mean()
            avg_false = report[~report[col]][metric].mean()
            ratio = avg_true / avg_false
            records.append(dict(hparam=col, avg_true=avg_true, avg_false=avg_false, ratio=ratio))

    flag_report = pd.DataFrame(records).set_index("hparam")
    flag_report.sort_values("ratio", ascending=False, inplace=True)
    if round_digits is not None:
        flag_report = flag_report.round(round_digits)

    return flag_report


def get_most_recent_folder(
    result_dir: Path = None, date_format: str = "%Y-%m-%d_%H-%M-%S", contains=None
):
    """Return the most recent directory based on the date in the folder name."""

    if result_dir is None:
        result_dir = RESULTS_DIR

    most_recent_folder = None
    most_recent_time = datetime.min

    for item in result_dir.iterdir():
        if item.is_dir() and not item.name.startswith("_"):
            if contains is not None and contains not in item.name:
                continue
            try:
                folder_date = datetime.strptime("_".join(item.name.split("_")[:2]), date_format)
                if folder_date > most_recent_time:
                    most_recent_time = folder_date
                    most_recent_folder = item
            except (ValueError, IndexError):
                continue

    return most_recent_folder


def display_report(
    report: pd.DataFrame,
    apply_shrink_columns: bool = True,
    copy_to_clipboard: bool = True,
    rename_bool_flags: bool = True,
):
    """Display the report in a nicer-ish format.

    To be able to wrap col names we need to use set_wrap_stype, which returns a
    styled df, and doesn't behave like a normal df. For encapsulate the displaying in
    this function.

    Args:
        report: The report to display
        apply_shrink_columns: Make the column more compat by replacing
            underscores with newlines
        copy_to_clipboard: Copy the report to the clipboard
        rename_bool_flags: Rename the boolean flags to be more compact and readable
    """
    report = report.copy()

    if apply_shrink_columns:
        report = shrink_columns(report)

    if rename_bool_flags:
        report = _rename_bool_flags(report)

    if copy_to_clipboard:
        to_clipboard(report)

    report.reset_index(inplace=True)

    styled_report = set_wrap_style(report)

    display(styled_report)


def shrink_columns(df, also_wrap_index=True):
    """Make the column names more compact by replacing underscores with newlines"""
    df = df.copy()

    df.columns = [col.replace("_", "\n") for col in df.columns]
    if also_wrap_index:
        df.index.names = [name.replace("_", "\n") for name in df.index.names]

    # Define a formatter function that formats float numbers without trailing zeros
    def formatter(x):
        if isinstance(x, float):
            return "{:.10f}".format(x).rstrip("0").rstrip(".")
        return x

    return df.map(formatter)


def set_wrap_style(df):
    return df.style.set_table_styles([{"selector": "th", "props": [("white-space", "pre-wrap")]}])


# ------------
# Error Utils
# ------------


def map_err_key(err_msg):
    if err_msg is None:
        return err_msg

    regex_replacements = [
        (
            r"your messages resulted in \d+ tokens",
            "your messages resulted in x tokens",
        ),
        (
            r"(?<=Exception uncaught by agent or environment in task\s)([^\s]+)",
            "<task_name>.",
        ),
    ]

    for pattern, replacement in regex_replacements:
        err_msg = re.sub(pattern, replacement, err_msg)
    return err_msg


def error_report(df: pd.DataFrame, max_stack_trace=10):
    """Report the error message for each agent."""

    if "err_key" not in df:
        df["err_key"] = df["err_msg"].map(map_err_key)

    unique_counts = df["err_key"].value_counts().sort_values(ascending=False)
    report = []
    for err_key, count in unique_counts.items():
        report.append("-------------------")
        report.append(f"{count}x : {err_key}\n")
        # find sub_df with this error message
        sub_df = df[df["err_key"] == err_key]
        idx = 0

        exp_result_list = [get_exp_result(row.exp_dir) for _, row in sub_df.iterrows()]
        task_names = [exp_result.exp_args.env_args.task_name for exp_result in exp_result_list]

        # count unique using numpy
        unique_task_names, counts = np.unique(task_names, return_counts=True)
        task_and_count = sorted(zip(unique_task_names, counts), key=lambda x: x[1], reverse=True)
        for task_name, count in task_and_count:
            report.append(f"{count:2d} {task_name}")

        report.append(f"\nShowing Max {max_stack_trace} stack traces:\n")
        for exp_result in exp_result_list:
            if idx >= max_stack_trace:
                break
            # print task name and stack trace
            stack_trace = exp_result.summary_info.get("stack_trace", "")
            report.append(f"Task Name: {exp_result.exp_args.env_args.task_name}\n")
            report.append(f"exp_dir: {exp_result.exp_dir}\n")
            report.append(f"Stack Trace: \n {stack_trace}\n")
            report.append("\n")
            idx += 1

    return "\n".join(report)


def categorize_error(row):
    if pd.isna(row.get("err_msg", None)):
        return None
    for category, check_function in ERR_CLASS_MAP.items():
        if check_function(row["err_msg"], row["stack_trace"]):
            if category == "critical_server_error":
                return is_critical_server_error(
                    row["err_msg"], row["stack_trace"], return_error_type=True
                )
            elif category == "minor_server_error":
                return is_minor_server_error(
                    row["err_msg"], row["stack_trace"], return_error_type=True
                )
            return category
    return "other_error"


def error_report_detailed(df: pd.DataFrame, max_stack_trace=10):
    """Report the error message for each agent, categorizing them as server errors or retry errors."""

    df["error_category"] = df.apply(categorize_error, axis=1)

    report = []
    for category in df["error_category"].unique():
        if category is None:
            continue
        report.append("\n-------------------")
        report.append(f"Category: {category}")
        report.append("-------------------\n")
        report.append(f"Total number of errors: {len(df[df['error_category'] == category])}\n")
        category_df = df[df["error_category"] == category]
        unique_counts = category_df["err_msg"].value_counts().sort_values(ascending=False)

        idx = 0
        for err_msg, count in unique_counts.items():
            if idx >= max_stack_trace:
                break
            idx += 1
            report.append("-------------------")
            report.append(f"{count}x : {err_msg}\n")
            sub_df = category_df[category_df["err_msg"] == err_msg]
            for _, row in sub_df.iterrows():
                exp_result = ExpResult(row.exp_dir)
                report.append(f"Task Name: {exp_result.exp_args.env_args.task_name}\n")
                report.append(f"exp_dir: {exp_result.exp_dir}\n")
                report.append(f"Stack Trace: \n {row['stack_trace']}\n")
                report.append("\n")
                break

    return "\n".join(report)


def print_errors_chronologically(df: pd.DataFrame):
    """Print the errors in chronological order, grouping contiguous chunks of the same error."""
    df = df.sort_values("exp_date", ascending=True)

    current_error = None
    error_count = 0

    for _, row in df.iterrows():
        if pd.isna(row.get("err_msg", None)):
            continue

        error = categorize_error(row)

        if error != current_error:
            if current_error is not None:
                print(f"{current_error.ljust(40)} : {str(error_count).rjust(5)} times")

            current_error = error
            error_count = 1
        else:
            error_count += 1

    if current_error is not None:
        print(f"{current_error.ljust(40)} : {str(error_count).rjust(5)} times")


def report_different_errors(sub_df):
    """Report the different errors in the dataframe."""

    def _categorize_error(row):
        if pd.isna(row.err_msg):
            record = {}
        else:
            record = {
                err_class: err_fn(row.err_msg, row.stack_trace)
                for err_class, err_fn in ERR_CLASS_MAP.items()
            }
            record["other_err"] = np.sum(list(record.values())) == 0
            record["any_err"] = True

        return pd.Series(record)

    error_report = sub_df.apply(_categorize_error, axis=1).sum(skipna=True)

    # TODO: fix this bug
    assert isinstance(error_report, pd.DataFrame), "Expected a DataFrame, got a Series."

    return error_report


def split_by_key(df: pd.DataFrame, key, force_at_leaste_one_variable=True):
    """Return a dict of dataframes spearted by the given key."""
    # check if key in df
    if not (key in df.columns):
        df = df.reset_index(key, inplace=False)

    df_dict = {}
    for value in df[key].unique():
        sub_df = df[df[key] == value].copy()
        set_index_from_variables(sub_df, force_at_leaste_one_variable=force_at_leaste_one_variable)
        df_dict[value] = sub_df

    return df_dict


def set_task_category_as_index(result_df, task_category_map=TASK_CATEGORY_MAP):
    """Create task_category index from task_name if needed and re-assign index
    from variables using task_category."""
    # rested index task_name (level 0)
    new_df = result_df.reset_index(inplace=False)
    if not "task_category" in new_df.columns:
        new_df["task_category"] = new_df["env_args.task_name"].map(task_category_map)
    set_index_from_variables(new_df, task_key="task_category")
    return new_df
