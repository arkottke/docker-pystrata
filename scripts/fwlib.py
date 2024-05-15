#!/usr/bin/python3
# cloudburst framework - Bruce Hearn 2021 bruce.hearn@gmail.com
# multithreading
import concurrent.futures
import json
import os.path
import shutil
import subprocess
from pathlib import Path
from typing import List

import jsonschema
import s3lib
import ziplib

# from multiprocessing import Pool

# this variable determines the default behavior, to exit when an error is found. Individual tasks override this behavior
EXIT_ON_ERROR = True


# get the input data for all the sites we are going to process
def process_fetches(mode: str, fetches: list, prior_errors: bool = False):
    return_code = 0

    # TODO: move elsewhere or change default
    remove_zips = True

    for fetch in fetches:
        required = False
        if "required" in fetch:
            required = fetch["required"]
        # skip a store task when there are prior errors UNLESS task is required
        if not required and prior_errors:
            continue

        exit_on_error = EXIT_ON_ERROR
        if "exitOnError" in fetch:
            exit_on_error = fetch["exitOnError"]

        name: str = fetch["name"]

        if "includeWhenMode" in fetch:
            include_when_mode = fetch["includeWhenMode"]
            if mode not in include_when_mode:
                print(f"skipping fetch task {name} in mode {mode}")
                continue
        if "excludeWhenMode" in fetch:
            exclude_when_mode = fetch["excludeWhenMode"]
            if mode in exclude_when_mode:
                print(f"skipping fetch task {name} in mode {mode}")
                continue

        bucket: str = fetch["bucket"]
        key: str = fetch["key"]
        dest: str = fetch["dest"]

        expand = False
        if "expand" in fetch:
            expand = fetch["expand"]

        if expand:
            # allows the user to specify a directory for dest path
            if key.endswith(".7z") and not dest.endswith(".7z"):
                dest = os.path.join(dest, os.path.basename(key))

        b_fetch = True
        if dest.endswith(".7z") and Path(dest).exists():
            # if the file already exists in place, we will not re-fetch it
            b_fetch = False

        # fetch file from S3
        if b_fetch:
            rc = s3lib.get_files(bucket, key, dest, filter=None)
            # return_code = s3lib.copy_s3_object(bucket, key, dest)

        if exit_on_error and rc != 0:
            return_code = rc
            break
        elif expand:
            # unzip the inputs, prepare input files
            is_expanded = False
            if dest.endswith(".7z"):
                expand_to = Path(dest).parent
            else:
                # if dest does not end with 7z, it may be a directory tree with 7z files to expand
                p_dest = Path(dest)
                if p_dest.is_dir():
                    for zip in p_dest.rglob("*.7z"):
                        return_code = ziplib.expand(zip, zip.parent)
                        if exit_on_error and return_code != 0:
                            break
                        elif remove_zips:
                            zip.unlink()
                    is_expanded = True

            if not is_expanded:
                rc = ziplib.expand(dest, expand_to)

                if exit_on_error and rc != 0:
                    return_code = rc
                    break
                elif remove_zips:
                    if len(dest) > 3 and dest[-3:] == ".7z":
                        os.remove(dest)

        if "excludeFilePattern" in fetch:
            patterns = fetch["excludeFilePattern"]
            files = [
                f
                for f in Path(dest.replace(".7z", "")).iterdir()
                if any(f.match(p) for p in patterns)
            ]
            for file in files:
                print(f"removing file: {file}")
                os.remove(file)

    return return_code


def run_tasks(process_list: list, mode: str, prior_errors: bool = False):
    logFolder = "./logs"
    return_code = 0

    # create logs folder if it doesn't exist
    os.makedirs(logFolder, exist_ok=True)

    for process in process_list:
        required = False
        if "required" in process:
            required = process["required"]
        # skip a store task when there are prior errors UNLESS task is required
        if not required and prior_errors:
            continue

        exit_on_error = EXIT_ON_ERROR
        if "exitOnError" in process:
            exit_on_error = process["exitOnError"]

        # apply run mode logic - skip processes as needed
        proc_name = process["name"]

        if "includeWhenMode" in process:
            include_when_mode = process["includeWhenMode"]
            if mode not in include_when_mode:
                print(f"skipping process task {proc_name} in mode {mode}")
                continue
        if "excludeWhenMode" in process:
            exclude_when_mode = process["excludeWhenMode"]
            if mode in exclude_when_mode:
                print(f"skipping process task {proc_name} in mode {mode}")
                continue

        # create the output directory when provided
        output_folder = None
        if "outputFolder" in process:
            output_folder = process["outputFolder"]
            os.makedirs(output_folder, exist_ok=True)

        # generate index of input files, when file pattern is specified
        file_pattern = None
        if "inputFilePattern" in process:
            file_pattern = process["inputFilePattern"]

        if file_pattern == None:
            # create an empty work list so that we execute the command that was provided
            work_list = [""]
        else:
            input_folder = process["inputFolder"]
            work_list = []
            # get files - recursive matches
            files = Path(input_folder).rglob(file_pattern)
            for file in files:
                work_list.append(file)

            if len(work_list) == 0:
                print(
                    f"Error preparing {proc_name} work list. No files found in {file_pattern}"
                )
                if exit_on_error:
                    return_code = 232
                    break

        log_behavior = None
        if "logBehavior" in process:
            log_behavior = process["logBehavior"]

        workers = 0
        if "workers" in process:
            workers = process["workers"]

        timeout = None
        if "timeout" in process:
            timeout = process["timeout"]
            if timeout <= 0:
                timeout = None

        # run the current process
        rc = manage_process(
            proc_name,
            work_list,
            process["command"],
            log_behavior,
            workers,
            timeout,
            exit_on_error,
        )
        if exit_on_error and rc != 0:
            print("errors found processing " + proc_name + ", ending early")
            return_code = rc
            break

    return return_code


# delegate for running external executables
def process_runner(process_name: str, item: int, items: int, timeout: int, cmd: str):
    escapedCmd = cmd.replace("\n", "\\n")
    print(f"starting: [{process_name}] #{item}/{items} [{escapedCmd}]")
    return subprocess.run(cmd, shell=True, timeout=timeout)


# ************************************************************************************************************
# manageProcess
# manages the execution of programs across the available CPUs
# ************************************************************************************************************
def manage_process(
    process_name: str,
    work_list: list,
    command: str,
    log_behavior: str,
    workers: int,
    timeout: int,
    exit_on_error: bool,
):
    return_code = 0
    log_folder = "logs"
    counter = 0

    # read in the index file, which list the files to run
    process_count = len(work_list)

    # count the processors once, and run with all
    processor_count = len(os.sched_getaffinity(0))
    if workers <= 0:
        workers = processor_count

    # if there are fewer processes to run than processors, use only processCount threads
    if process_count < workers:
        workers = process_count

    print(
        f"processes to run: {process_count}, processors available: {processor_count}, concurrent workers: {workers}"
    )

    futures = []
    with concurrent.futures.ThreadPoolExecutor(max_workers=workers) as executor:
        for inputFilePath in work_list:
            counter += 1

            cmd = command.replace("[INPUT_FILE_PATH]", str(inputFilePath))

            if log_behavior == "capture":
                log_file_str = (
                    str(inputFilePath)
                    .replace("/", "-")
                    .replace(".in", "")
                    .replace(".txt", "")
                )
                log_file_out = os.path.join(
                    log_folder, process_name + "-" + log_file_str + ".log"
                )
                log_file_err = os.path.join(
                    log_folder, process_name + "-" + log_file_str + ".err"
                )
                cmd += f" >{log_file_out} 2>{log_file_err}"

            futures.append(
                executor.submit(
                    process_runner, process_name, counter, len(work_list), timeout, cmd
                )
            )

        for future in concurrent.futures.as_completed(futures):
            try:
                process_result = future.result()
                if process_result.returncode != 0:
                    if exit_on_error:
                        return_code = process_result.returncode
                        print(
                            f"error: process returned return code: {process_result.returncode}"
                        )
                    else:
                        print(
                            f"warning: process returned return code: {process_result.returncode}"
                        )
            except Exception as err:
                print(f"error of type [{type(err)}] in process: {str(err)}")
                if exit_on_error:
                    return_code = 244

    # remove any empty err files
    files = Path(log_folder).glob(f"{process_name}-*.err")
    for file in files:
        if Path(file).stat().st_size == 0:
            os.remove(file)

    if return_code != 0:
        # post-process the error log files. report any non-empty error files
        print(f"error running {process_name}...")
        files = Path(log_folder).glob(f"{process_name}-*.err")
        logs = ""
        for file in files:
            with open(file) as myfile:
                a_errs = myfile.readlines()
            errs = "\n".join(map(str, a_errs))

            log_file = str(file).replace(".err", ".log")
            if Path(log_file).stat().st_size > 0:
                with open(log_file) as myfile2:
                    a_logs = myfile2.readlines()
                if len(a_logs) > 10:
                    # only display the last 10 lines
                    a_logs = a_logs[len(a_logs) - 10 : len(a_logs) - 1]
                logs = "\n".join(map(str, a_logs))

            subject = f"errors found processing {process_name}, file: {file}"
            message = f"contents: {logs}\nErrors:\n{errs}"

            print(subject + ". " + message)
    return return_code


def move_files(move_tasks: List[dict], mode: str, prior_errors: bool = False):
    return_code = 0

    for task in move_tasks:
        required = task.get("required", False)
        # skip a store task when there are prior errors UNLESS task is required
        if not required and prior_errors:
            continue

        exit_on_error = task.get("exitOnError", EXIT_ON_ERROR)

        name = task["name"]

        if "includeWhenMode" in task:
            include_when_mode = task["includeWhenMode"]
            if mode not in include_when_mode:
                print(f"skipping move task {name} in mode {mode}")
                continue

        if "excludeWhenMode" in task:
            exclude_when_mode = task["excludeWhenMode"]
            if mode in exclude_when_mode:
                print(f"skipping move task {name} in mode {mode}")
                continue

        input_folder = task["inputFolder"]
        include_file_pattern = task["includeFilePattern"]
        output_folder = task["outputFolder"]

        exclude_file_pattern = task.get("excludeFilePattern", None)

        n_moved = 0
        input_path = Path(input_folder)
        if input_path.exists():
            for includePattern in include_file_pattern:
                for file in input_path.rglob(includePattern):
                    if exclude_file_pattern is None or not (
                        True in [file.match(p) for p in exclude_file_pattern]
                    ):
                        try:
                            in1 = str(input_path)
                            out1 = str(Path(output_folder))
                            output_path = out1
                            # print(f'{file} / {in1}')
                            if str(file).startswith(in1):
                                # add one to include the trailing '/'
                                file_part = str(file)[len(in1) + 1 :]
                                output_path = Path(out1).joinpath(file_part)
                                # print(f'{output_path}')
                            os.makedirs(output_path.parent, exist_ok=True)

                            if n_moved == 0:
                                print(f"moving {file} (and others) to {output_path}")

                            shutil.move(str(file), output_path)
                            n_moved += 1
                        except Exception as err:
                            err_str = f"failed to move {str(file)} to {output_folder}, error: {str(err)}"
                            if exit_on_error:
                                print(f"error: {err_str}")
                                return 213
                            else:
                                print(f"warning: {err_str}")
        if n_moved == 0:
            print(f"warning: no files moved from {input_folder} to {output_folder}")
        else:
            print(f"moved {n_moved} files from {input_folder} to {output_folder}")

    return return_code


def process_store(tasks_store: list, mode: str, prior_errors: bool = False):
    return_code = 0

    for task in tasks_store:
        required = task.get("required", False)
        # skip a store task when there are prior errors UNLESS task is required
        if not required and prior_errors:
            continue

        exit_on_error = task.get("exitOnError", EXIT_ON_ERROR)
        name = task["name"]

        if "includeWhenMode" in task:
            include_when_mode = task["includeWhenMode"]
            if mode not in include_when_mode:
                print(f"skipping storage task {name} in mode {mode}")
                continue

        if "excludeWhenMode" in task:
            exclude_when_mode = task["excludeWhenMode"]
            if mode in exclude_when_mode:
                print(f"skipping storage task {name} in mode {mode}")
                continue

        bucket = task["bucket"]
        dest = task["dest"]
        source = task["source"]

        compress = task.get("compress", False)
        compress_sub_directories = task.get("compressSubDirectories", False)
        remove_on_store = task.get("removeOnStore", True)
        zip_shared_memory = task.get("compressInSharedMemory", False)

        if not Path(source).exists():
            print(
                f"error: source path for store task [{name}] does not exists: {source}"
            )
            if exit_on_error:
                return_code = 43
                break
        else:
            contents = []
            is_empty = False
            if Path(source).is_dir():
                contents = list(Path(source).glob("*"))
                if not compress_sub_directories:
                    # is there anything to zip?
                    is_empty = len(contents) == 0
                else:
                    # when compressing subdirectories, pre-check that at least one exists
                    for item in contents:
                        if item.is_dir() and len(list(item.glob("*"))) > 0:
                            is_empty = False
                            break

            if is_empty:
                print(
                    f"skipping empty output directory for storage task [{name}]: {source}"
                )
            else:
                print(f"saving outputs: {source}")

                if compress_sub_directories and len(contents) > 0:
                    for dir in contents:
                        if dir.is_dir():
                            src = str(dir)

                            # trim trailing / character
                            if src[-1] == "/":
                                src = src[0:-1]

                            if zip_shared_memory:
                                if src[0] == ".":
                                    src = src[1:]
                                if src[0] == "/":
                                    src = src[1:]
                                tmp_zip = "/dev/shm/" + src + ".7z"
                            else:
                                tmp_zip = src + ".7z"

                            rc = ziplib.compress(source_path=src, zip_path=tmp_zip)
                            if exit_on_error and rc != 0:
                                return_code = rc
                                break

                            key = Path(dest).joinpath(Path(tmp_zip).name)

                            rc = s3lib.write_s3_object(
                                bucket_name=bucket, key=str(key), file=tmp_zip
                            )
                            if exit_on_error and rc != 0:
                                return_code = rc
                                break

                            if remove_on_store:
                                os.remove(tmp_zip)
                elif compress:
                    src = str(Path(source))
                    # trim trailing / character
                    if src[-1] == "/":
                        src = src[0:-1]
                    if zip_shared_memory:
                        if src[0] == ".":
                            src = src[1:]
                        if src[0] == "/":
                            src = src[1:]
                        tmp_zip = "/dev/shm/" + src + ".7z"
                    else:
                        tmp_zip = src + ".7z"

                    rc = ziplib.compress(source_path=src, zip_path=tmp_zip)
                    if exit_on_error and rc != 0:
                        return_code = rc
                        break

                    if dest[-1] == "/":
                        key = Path(dest).joinpath(Path(tmp_zip).name)
                    else:
                        key = dest

                    rc = s3lib.write_s3_object(
                        bucket_name=bucket, key=str(key), file=tmp_zip
                    )
                    if exit_on_error and rc != 0:
                        return_code = rc
                        break

                    if remove_on_store:
                        os.remove(tmp_zip)
                else:
                    if Path(source).is_dir():
                        rc = s3lib.put_files(
                            bucket_name=bucket, local_folder=source, prefix=dest
                        )
                    else:
                        # handle case where a directory name is specified for the destination
                        if dest[-1] == "/":
                            key = Path(dest).joinpath(Path(source).name)
                        else:
                            key = dest

                        rc = s3lib.write_s3_object(
                            bucket_name=bucket, key=str(key), file=source
                        )
                    if exit_on_error and rc != 0:
                        return_code = rc
                        break

    return return_code


def get_validated_task_config(json_data_path: str):
    cfg = None
    script_dir = Path(__file__).parent
    json_schema_path = script_dir.joinpath("tasks.schema.json")

    if json_data_path is None or json_data_path == "":
        # default TASKS FILE
        json_data_path = script_dir.joinpath("tasks.json")
    else:
        json_data_path = Path(json_data_path)

    if json_data_path.exists():
        with open(json_data_path, "r") as file:
            # do environment variable parameter substitution here
            tasks_json = os.path.expandvars(file.read())
            cfg = json.loads(tasks_json)

        if not json_schema_path.exists():
            print(
                f"warning, skipping validation of json against schema, cannot find schema file: {json_schema_path}"
            )
        else:
            with open(json_schema_path, "r") as file:
                tasks_schema = file.read()
                schema = json.loads(tasks_schema)
            try:
                jsonschema.validate(instance=cfg, schema=schema)
            except jsonschema.exceptions.ValidationError as err:
                print(f"error, cannot validate json schema: {err}")
                return None
    return cfg
