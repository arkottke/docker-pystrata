# PG&E Cloudburst Framework

The PGE Cloudburst Framework is used to automate the execution of programs and scripts at scale using Amazon
AWS Batch. It can be used to run a series of programs across tens, hundreds or even thousands of servers
concurrently. The framework makes it easy to run a process that gathers input data, processes it, and stores
results for later analysis.

To fully use the framework, you will need to install and configure a number of tools.

- Git, to interact with github
- An editor, such as JetBrains PyCharm or Microsoft Visual Studio Code
- the Amazon AWS CLI (command-line interface)
- Terraform, for configuring AWS
- Python 3.9 or higher, with a couple of python modules

The installation steps are documented below.

## How to Get Started

- decide on a unit of work. For instance, a single run of a single program, or a sequence of programs operating on
  common data. Is there a parameter or two that specifies this unit of work? The unit of work should take less than 10
  hours to run.
- decide on a name for your project e.g. "projectx"
- develop the programs/scripts to perform the unit of work
- define a set of input data
- define a parameter (or several parameters) to control the execution.

## Install the tools

installation involves a number of packages. These can be either downloaded as installers from the web or installed
by a command-line tool. For command-line installation on the mac, homebrew is recommended. On the pc, chocolatey
is recommended. In Linux, you can use your favorite package manager.

0. on windows?
   - install chocolatey
     - https://chocolatey.org
   - install make: from an **admin powershell prompt**:
     - `choco install make`
1. install git
   - https://git-scm.com/book/en/v2/Getting-Started-Installing-Git
   - mac: (included when you install xcode command line tools)
   - win: `choco install git`
   - Configure your GIT name and email address. Open a command prompt
     - `git config --global user.name "John Doe"`
     - `git config --global user.email johndoe@example.com`
2. install python 3.9+
   - https://www.python.org/downloads/
   - mac: `brew install python`
   - win: `choco install python`
3. install a python package manager, e.g. pip. Add the boto3 and json schema packages
   - `pip install boto3 jsonschema`
4. install the AWS CLI
   - https://docs.aws.amazon.com/cli/latest/userguide/getting-started-install.html
   - mac: `brew install awscli`
   - win: `choco install awscli`
5. install terraform
   - https://www.terraform.io/downloads.html
   - mac: `brew install terraform`
   - win: `choco install terraform`
6. install 7zip and ensure `7z` is in the path
   - https://www.7-zip.org/download.html
   - mac: `brew install p7zip`
   - win: `choco install 7zip.install`
7. install docker desktop
   - https://docs.docker.com/desktop/
8. install an editor of your choice (optional)
   - JetBrains Pycharm https://www.jetbrains.com/pycharm/
   - Microsoft Visual Studio Code https://code.visualstudio.com/

## Configure the environment

### fork or subtree the cloudburst repo

a. are you creating a new repo? you can fork the cloudburst repo
and use this structure to develop your project. This can be done from the
github: https://github.com/bh3791/cloudburst

To get updates from the cloudburst repo later, use the github site to
merge the updates, or follow these manual steps:

        git fetch upstream master
        git pull upstream master --squash

### existing repo: subtree

1.  use an existing github repo. Use `git subtree` to clone the cloudburst repo as a directory
    subtree in your repo. From a command prompt in your repo, first define a remote (shortcut):

            git remote add -f cloudburst https://github.com/bh3791/cloudburst.git

- Next, add the subtree:

  git subtree add --prefix cloudburst cloudburst master

- To update the subtree later on:

  git fetch cloudburst master
  git subtree pull --prefix cloudburst cloudburst master --squash

- you can even push changes back up to the remote cloudburst repo, being careful to merge
  any customizations. This is safest to do if you **first fork the cloudburst repo**, push to your
  fork, and then use a pull request to request the changes get into the main repo.

      git subtree push --prefix=cloudburst https://github.com/<your_name>/cloudburst.git master --squash

- when you use subtree, you will get the default Makefile, Dockerfile and docker-compose.yml files in the cloudburst
  subdirectory. It is best to copy these files to your repo root directory, and then customize them,
  or merge them with your existing files, rather than use them in-place.

2.  run the `aws configure` command to set up your security credentials. You will need to generate these in
    the AWS console https://console.aws.amazon.com/iamv2/home#/users : user : security credentials : access keys
3.  edit the `Makefile`, naming the TAG and REPO_ID 'projectx' and your AWS_ID (account id) at the top
4.  configure terraform by editing the `terraform.tfvars` file, naming the deployment 'projectx'. Create the infrastructure when you are satisfied. The project is initially configured to work out of the box in the us-west-2 region. To modify it for another region, networking.tf would need to be edited to apply the correct availability zones and subnets.

        cd terraform
        terraform init
        terraform plan
        terraform apply

5.  create one or more buckets to store input/output data e.g. 'projectx_test'

        aws s3 mb projectx_test

## Configuring your process with tasks.json

The easiest way to approach this is to start by creating a functioning docker container
that contains the scripts/executables you want. However, you may not yet be accessing S3 to retrieve and store
the input and output data.

To use the cloudburst framework, you will need to edit your Dockerfile to add the scripts
and define the entrypoint as the framework entrypoint. The framework then uses
the file `scripts/tasks.json` to retrieve data, run your scripts, and then store the data.
For example, a simple scenario might be:

- copy input data from S3 (requiring you to set up an S3 bucket and load it with input data)
- run a series of programs/scripts,
- and store output data back to S3.

These tasks are configured in the json file. You can refer to the json schema file using a schema
friendly editor to edit the file. The tasks types are `fetch, tasks, move, store` and can be
specified in any order:

- fetch: retrieves a file, or files, from an S3 storage bucket and (optionally) unzip it with 7zip.
- tasks: runs a shell script or other command of your choice. This can be multithreaded across the n cores
  on the instance when a list of input files is specified.
- store: stores a file, or files, to an S3 storage bucket, optionally using 7zip to compress.
- move: moves files from one folder to another.

The `extras/` folder contains a few examples of the tasks.json from simple to complex. The tasks.json file
uses parameter substitution using the form `{ENV_VARIABLE_NAME}`.

### The unit of work (WORK_ITEM)

When you start a new job, the most important parameter is the unit of work. This is a string passed by the
`start_jobs.py` script to the batch framework and set as the `WORK_ITEM` environment variable in the docker container.
This parameter is what allows you to define the unit of work. It is intended to be used in your `tasks.json` file to
control the process logic. The unit of work is user-defined, and may be a "site number," "file path," or some other
unit that we are processing. Thus it can be used to fetch a specific zip file or directory from S3, pass to your
program, or store files to S3. The following example shows a fetch task that will download and unzip the specified
WORK_ITEM.7z file to the ./Sites/WORK_ITEM folder:

        {
            "name" : "get-input-files",
            "bucket" : "${BUCKET_NAME}",
            "key" : "input/${WORK_ITEM}.7z",
            "dest" : "./Sites/${WORK_ITEM}.7z",
            "expand" : true
        },

### MODE: conditional task execution

When you start a batch of jobs, you can specify what `mode` to run them in. Mode is an optional, user-defined
parameter ("default" when not specified) that allows you to conditionally run tasks. This `MODE_STR` environment variable is
set in the docker container at the beginning of each task. Each task type includes the options `includeWhenMode`
and `excludeWhenMode`. This provides control over when a task is run.

For example, a process involves a main fortran program and a separate post-processor program, storing the results of
both to S3. At times, you want to rerun the post-processor but not the main program. So you can define a mode called
full, and one called post. To the main program entry, you can add the directive:

      "excludeWhenMode": "post"

You will also need to add a conditional `fetch` to copy in the previous main output from S3. You will likely also need
to add a condition to exclude the main "store" task when in "post" mode. The example `tasks-haz-dams.json` provides an
example that illustrates this concept.

### Multi-processing a set of input files

The following example shows a hazard analysis program looping over a set of input files matching 'haz-\*.in' in the
./Sites/WORK_ITEM/ folder. When there are n VCPUs present, n processes will be run concurrently until they are all
complete. When specified, the outputFolder will be pre-created before running the program. This is useful for
processes (such as fortran programs) that expect directories to be pre-created. It is also possible to provide your
own shell script if you wish to further customize this process. The special macro `[INPUT_FILE_PATH]` is used to
substitute the name of each input file from the input files matched in `inputFilePattern` so it can be used in a
command string. In this example, it is shown with two prepended zero-linebreak sequences, supporting programs
that traditionally takes user input in response to prompts, but which must do so in an automated way here.

        {
            "name" : "haz",
            "excludeWhenMode" : "post",
            "command" : "echo '0\n0\n[INPUT_FILE_PATH]' | /opt/haz/haz",
            "inputFolder" : "Sites/${WORK_ITEM}",
            "inputFilePattern" : "haz-*.in",
            "outputFolder" : "./Output/${WORK_ITEM}"
        },

### Ensuring Continuity: 'exitOnError' and 'required' task attributes

It can be useful to ensure a step is always taken regardless of earlier errors. There are two mechanisms
to help with this: `"exitOnError": false` and `"required": true`. When exitOnError is set to false, an error
that occurs during a processing step may be reported but it will not prevent the execution of subsequent tasks.
Furthermore, it will not by iteself cause the overall processing to end in an error.

The `"required": true` setting is especially useful if you wish to ensure storage tasks run, for storing logs to
S3 or ensuring that partial results can be stored.

## Passing parameters from the client to use in tasks.json and your processes

The framework passes parameters as environment variables into docker. This is true for local testing using
`docker-compose.yml` and also true when starting an AWS batch job with `start_jobs.py`. The framework
only absolutely requires a single parameter: `AWS_REGION=us-west-2` (or the region of your choice)
but other parameters that the `start_jobs.py` script pass through are `BUCKET_NAME` and `MODE_STR` which
define the name of the S3 bucket to use and the mode that the program is running in, if specified.

        BUCKET_NAME=my-bucket
        DISK_STATS=0
        MODE_STR=full

In most cases it will be necessary to define a parameter that defines the unit of work. In the `start_jobs.py`
script this is anticipated and is called `WORK_ITEM`, though it is an optional parameter. If more parameters
are necessary the script must be modified.

        WORK_ITEM=test1

The `start_jobs.py` script has a parameter called `-name-value`, which can be used to specify custom environment
variables in your AWS Batch docker container. The framework can access these variables by using parameter
substitution in your `tasks.json` file, e.g. to specify the location of an S3 path or an addition parameter to
pass into your program/script. See the example below for more details.

## Using the client scripts

The following steps illustrate the use of some of the client scripts. A typical cloudburst process would
involve storing input data in S3, running a series of programs in the docker container, and then storing
results to S3. But you could design a process to pull from other web servers and store to whatever place you wish.

### validate the `tasks.json` file you created against the tasks schema

    jsonschema scripts/tasks.schema.json -i scripts/tasks.json -o plain

### Build and test the docker container locally using `docker-compose.yml` to hold the parameters.

    make test

### When you are satisfied with the docker container, upload it to ECR

    make push

### Compress the input data

    python scripts/compress_inputs.py -source-folder ./source.tmp -zip-folder ./input.tmp -filter 'faultfiles'
    python scripts/compress_inputs.py -source-folder ./source.tmp -zip-folder ./input.tmp -filter 'Dam*/Period*'

### Upload input data to S3

You can upload files using the upload_inputs script or with the AWS CLI:

    python scripts/upload_inputs.py -bucket projectx_test -local-folder ./input.tmp -prefix 'input/' -threads 10
    aws s3 cp ./input.tmp/ s3://projectx_test/input/

### Start a batch job

The `start_jobs` script is a powerful tool and has a number of options. Some examples are listed below:

The command will be preview-only until the `-apply` parameter is added.

    python scripts/start_jobs.py -bucket projectx_test -queue projectx_queue -jobdef projectx_jobdef -workitems Dam001/Period03 -mode full
    python scripts/start_jobs.py -bucket projectx_test -queue projectx_queue -jobdef projectx_jobdef -workitems 'Dam001/Period02,Dam001/Period02' -mode post

Use zero `-padding` of 2 with a prefix to specify a range of 16 work items of the form 'Site001/Period01 - Site001/Period16'

    python scripts/start_jobs.py -bucket bruceh_test -queue cloudburst_queue -jobdef cloudburst_jobdef -workitems 01-16 -mode post -prefix Dam001/Period -padding 2

Pass the name of a work item file:

    python scripts/start_jobs.py -bucket projectx_test -queue projectx_queue -jobdef projectx_jobdef -mode full -workitemfile worklist.tmp

The `-workitemfile` parameter can use stdin, so you can also pipe a list of work items into start_jobs:

    cat worklist.tmp | python scripts/start_jobs.py -bucket projectx_test -queue projectx_queue -jobdef projectx_jobdef -mode full -workitemfile -

The AWS cli can be used to create a list of input files from S3 and pass the work item list to `start_jobs.py`:

    aws s3 ls s3://test-bruceh/input/ --recursive | cut -c 38-52 | python scripts/start_jobs.py -bucket projectx_test -queue projectx_queue -jobdef projectx_jobdef -mode full -workitemfile -

A custom work item generator can work to start_jobs:

    python extras/periodlist-gen.py -dams 001-010 -periods 01-16 | python scripts/start_jobs.py -bucket projectx_test -queue projectx_queue -jobdef projectx_jobdef -mode post -workitemfile -

Custom variables can be passed to the server as environment variables using the `-name-value` parameter. These can be used
in the `tasks.json` file using environment variable substitution, or accessed from your program/script. The example below shows
two variables being set:

    python scripts/start_jobs.py ... -name-value STORAGE_BUCKET=my_storage_bucket -name-value SERIES_NUMBER=21

### List the active batch jobs

    aws batch list-jobs --job-queue projectx_queue

### Stop batch jobs

    python scripts/stop_jobs.py -queue projectx_queue -all
    python scripts/stop_jobs.py -queue projectx_queue -job
    aws batch terminate-job --job-id <jobId> --reason 'user requested stop'

### Check the status of a specific aws job

    aws batch describe-jobs --jobs <jobId>

### Download files from an S3 folder

    python scripts/get_outputs.py -bucket projectx_test -prefix 'output/' -local-folder output.tmp -threads 10
    aws s3 cp s3://projectx_test/output/ ./output.tmp/

### Unzip output files

    python scripts/unzip_folder.py -zipdir 'output.tmp'

### get help on any of the above commands using --help

    python scripts/unzip_folder.py --help
    python scripts/unzip_folder.py --help

## pyStrata Example

The files within this repository demonstrate the use of cloudburst with
`pyStrata` to perform site response simulations. The following steps are used to
run the calculations.

1.  First, create the necessary input files. These provide the profiles and
    motions used in the analysis. For a specific study these would be modified.
    From the root directory run the following commands:

        python scripts/make_profiles.py
        python scripts/make_motions.py

    We can check that input files will have been created:

        ❯ ls data/input/\*
        data/input/motions:
        m5p0-r10km.pkl m5p0-r30km.pkl m5p0-r80km.pkl m6p0-r10km.pkl m6p0-r30km.pkl
        m6p0-r80km.pkl m7p0-r10km.pkl m7p0-r30km.pkl m7p0-r80km.pkl

        data/input/profiles:
        lower.pkl middle.pkl upper.pkl

    The naming convention uses '-' to separate components, which is also used by `clilib.py` to specify ranges.

2.  The `docker-compose.yml` file describes an example configuration state. Using
    `LOCAL_MODE=1` has the calculation skip the fetch or store tasks, which are mapped into the
    docker environment using the volumes entry. The `WORK_ITEM` describes the
    attributes of the job. If this example, I use a '/' to separate the name
    of the profile and the file name pattern for the motions to compute. This
    could be adjusted based on the specific workflow.

3.  From the directory (and if docker is installed), the docker environment can
    be started with `make test`. For this example, it should start the
    environment
    and run the calculation for the three motions. If you have an issue, or want
    to tinker inside the docker environment run `make run`. This will start a
    `bash` shell at the working directory with the environment set by the
    `docker-compose.yml`. At this point, the calculation details can be
    finalized prior to involving AWS.

4.  To use S3, we first need to upload the input files into an S3 bucket so that
    they can be retrieved by the image.

        aws s3 mb s3://docker-pystrata-test
        aws s3 sync data/input s3://docker-pystrata-test/input

    The tasks associated with fetching these files can be found in
    `scripts/tasks.json` file. Note that all profiles and motions are downloaded
    for each calculation. Alternatively, selected files could be downloaded by
    using the '-name-value' parameter, see [Start a batch job](#start-a-batch-job).
    In the `tasks.json` file steps showing the input and output files are added
    for illustrative purposes.

5.  Now, edit `docker-compose.yml` and set `LOCAL_MODE=0` and comment out
    attaching the input volume. Afterwards, rerun the calculation with `make test`.
    The inputs will now be downloaded from S3 and the outputs uploaded:

        docker-pystrata on  master [✘!?] via  (py311) took 1m22s
        ❯ aws s3 ls s3://docker-pystrata-test/output/
                                   PRE middle/

        docker-pystrata on  master [✘!?] via  (py311)
        ❯ aws s3 ls s3://docker-pystrata-test/output/middle
                                   PRE middle/

        docker-pystrata on  master [✘!?] via  (py311)
        ❯ aws s3 ls s3://docker-pystrata-test/output/middle/
                                   PRE m5p0-r10km/
                                   PRE m5p0-r30km/
                                   PRE m5p0-r80km/

        docker-pystrata on  master [✘!?] via  (py311)
        ❯ aws s3 ls s3://docker-pystrata-test/output/middle/m5p0-r10km/
        2024-05-15 21:30:58     551311 output.pkl
        2024-05-15 21:30:58     263040 response_spectrum-surf.csv.gz

6.  We push the image to the cloud, first by defining `AWS_ID` in the
    `Makefile` and then running:

        make terraform-apply
        make push

7.  We can then start the calculation queue with:

        python scripts/start_jobs.py -bucket docker-pystrata-test -queue cloudburst_queue -jobdef cloudburst_jobdef -workitems 'middle/m5p0-*'

    If that is successful and looks good. Repeat it and add `-apply`. Once it is
    started, you can go the AWS Batch console for the proper region, and watch
    the queue.

## Technologies used in cloudburst

### Docker Containers

Docker is a tool that allows you, by specifying a single configuration file (the `Dockerfile`), build, test and deploy
a working linux image with the tools needed to get your work done. These docker images create "container instances"
that can be run on your own PC or on a cloud server.

Start with a docker image with a docker image that includes python 3.9 or greater (debian:11, ubuntu:20.04,
python:3.9-slim-bullseye, continuumio/miniconda3). With the Dockerfile you would then add any pip-installable
python libraries to the image, and copy your own files into the image.

For a Gnu Fortran program, you would start with an image that includes python, and in the Dockerfile, add dependencies
such as gfortran and make. You can build the fortran programs as part of the image build process.

With a built docker image, you can run a container on your own machine and test it until you are satisfied it works.
Once satisfied, the same exact image can be deployed to a DockerHub Repository or Amazon ECR (Elastic Container
Repository) so that it can be pulled when as needed when running in the cloud.

### AWS Batch

AWS Batch uses docker containers to run batch jobs. These containers are stored and retrieved from Amazon ECR
(preferred) or DockerHub. Internally, AWS Batch uses the AWS Elastic Container Service (ECS) to run the containers.
Logs are written to Cloudwatch Logs. The AWS Batch dashboard is the place to go to monitor the status of a batch of jobs.

Batch uses a "compute environment", a "queue" and a "job definition." When you run a batch job, the job references the
job definition and you add the job to a queue, which allocates jobs to a compute environment. Each time a job runs,
a new container instance is created and the parameters from the job you create are passed in.

The batch compute environment specifies whether you will run jobs in Fargate or EC2, and in standard or spot instances.
The "job definition" that specifies the docker container, CPU/Memory (and to some extent Disk) resources, and any
default parameters such as environment variables.

#### Monitoring processes in the AWS Console Batch Dashboard

Batch allows you to monitor the running processes in a dashboard that shows a count of running, successful and failed
jobs. You can drill down to a particular job and see the logs being generated in real-time, or review them after they have run.

### S3 Cloud Storage

S3 is a cloud storage technology provided by Amazon. A common use case for the framework involves taking some input
files, running one or more executables/scripts, and then storing the outputs. The input and output
files (and even the executables) can be stored in S3. The framework makes it easy to retrieve and store
zipped or uncompressed data to S3.

### Terraform

Terraform is a company that developed a tool that allows you to create networking and computational
infrastructure based on .tf configuration files. Terraform works with many cloud providers such
as AWS and Azure. The framework provides terraform configuration files that create and manage
the infrastructure necessary to run AWS Batch jobs in AWS Fargate, from networking
(VPCs and security groups) to the creation of the ECR repository and Batch job definition.

The terraform config files sets up everything needed by AWS Batch. It can be complicated to set up AWS
Batch without such a template. The framework uses the "Fargate Spot" configuration by default, which means that
your process may be stopped during execution. A retry strategy is specified to permit the restart. You can change
the configuration to be a non-spot instance by configuring the `terraform/batch.tf` file.

**Framework Author: Bruce Hearn 2021 bruce.hearn@gmail.com**
