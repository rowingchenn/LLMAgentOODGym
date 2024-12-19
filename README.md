# LLMAgentOODGym
OOD benchmark study for LLM agents based on BrowserGym and AgentLab.

## Prerequisites

Make sure you have the following installed:
- [Git](https://git-scm.com/downloads)
- [Conda](https://docs.conda.io/projects/conda/en/latest/user-guide/install/index.html)

## Git

This project uses Git with submodules. Follow the instructions below to work with the main repository and its submodules.

### 1. Clone the Main Repository and Initialize Submodules

To clone the main repository along with its submodules, use:

```bash
git clone --recursive git@github.com:rowingchenn/LLMAgentOODGym.git
cd LLMAgentOODGym
```

If you have already cloned the main repository without submodules, you can initialize and update submodules manually with:

```bash
git submodule update --init --recursive
```

### 2. Making Changes in a Submodule

We have two submodules, `agent_lab` and `browser_gym`:

- [AgentLab](https://github.com/rowingchenn/AgentLab_OOD.git)
- [BrowserGym](https://github.com/rowingchenn/BrowserGym_OOD.git)

Our goal is to merge new code from ServiceNow into our project and make our own modifications, which will be pushed to our own forked repositories.

Here are the working guides, taking agent_lab for example:

1. Navigate to the submodule's directory:

   ```bash
   cd agent_ood_lab
   ```

2. Make your changes and stage them:

   ```bash
   git add .
   ```

3. Commit the changes in the submodule:

   ```bash
   git commit -m "Your commit message in the submodule"
   ```

4. Push the changes to the submodule's remote repository:

   ```bash
   git push origin main
   ```

### 3. Pulling Changes with Submodules

Before committing your code to the remote repository, always execute the following commands to ensure your code is fully up-to-date and conflicts are resolved:

```bash
git pull --recurse-submodules
git submodule update --remote --recursive
```

Run these commands, carefully resolve any conflicts that arise, and then proceed with your commit and push to the remote repository. This approach helps maintain compatibility with the latest changes in both the main repository and submodules.

## Setting up the Environment

### 1. Create a New Conda Environment

To set up the environment, first create a new Conda environment. Run the following command:

```bash
conda create -n <environment_name> python=3.12.7
```

Replace `<environment_name>` with a name of your choice for the new environment.

### 2. Activate the Conda Environment

Once the environment has been created, activate it using:

```bash
conda activate <environment_name>
```

### 3. Install Dependencies for Each Subproject

This project consists of two subprojects (`BrowserGym` and `AgentLab`). You need to install each subproject in editable mode to ensure that any local code changes are reflected immediately. Make sure you install agent_ood_lab first and then install agent_ood_gym!

#### 3.1 Install AgentLab

**Navigate to the AgentLab directory** and install it in editable mode:

   ```bash
   cd agent_ood_lab
   pip install -e .
   ```

#### 3.2 Install BrowserGym

**Navigate to the BrowserGym directory** and install it in editable mode:

   ```bash
   cd agent_ood_gym
   make install
   ```

#### 3.3 Install WorkArena

**Navigate to the WorkArena directory** and install it in editable mode:

   ```bash
   cd agent_ood_gym/agent_ood_gym/work_arena
   pip install -e .
   ```

You don't need to run workarena-install since the instance of ServiceNow has already set up. You can access the instance by setting the SNOW_INSTANCE_URL, SNOW_INSTANCE_UNAME and SNOW_INSTANCE_PWD environment variables below.

### 4. Configure Environment Variables

The project requires certain environment variables to be configured. You can add these variables to your `.bashrc` file so they are automatically loaded each time you start a new terminal session.

1. **Open `.bashrc` in an editor**:

   ```bash
   vim ~/.bashrc
   ```

2. **Add the following environment variables to the end of `.bashrc`**:

   ```bash
   # API config   
   export OPENAI_API_KEY="<Your_OpenAI_API_Key>"
   export OPENAI_API_BASE="https://api.shubiaobiao.cn/v1/"

   # ServiceNow config
   export SNOW_INSTANCE_URL="https://dev245396.service-now.com/"
   export SNOW_INSTANCE_UNAME="admin"
   export SNOW_INSTANCE_PWD="F/sNP0cY=g5x"
   
   # WebArena config
   BASE_URL="http://gpublaze.ist.berkeley.edu"
   export WA_SHOPPING="$BASE_URL:7770/"
   export WA_SHOPPING_ADMIN="$BASE_URL:7780/admin"
   export WA_REDDIT="$BASE_URL:9999"
   export WA_GITLAB="$BASE_URL:8023"
   export WA_WIKIPEDIA="$BASE_URL:8888/wikipedia_en_all_maxi_2022-05/A/User:The_other_Kiwix_guy/Landing"
   export WA_MAP="$BASE_URL:3000"
   export WA_HOMEPAGE="$BASE_URL:4399"

   # AgentLab config
   export AGENTLAB_EXP_ROOT="<root_dir>/LLMAgentOODGym/agent_ood_lab/benchmark_results"
   ```

3. **Apply the changes** by running:

   ```bash
   source ~/.bashrc
   ```

This ensures all required environment variables are set every time you start a new terminal session.


## Run Experiments 
### WebOOD
Run **[this script](https://github.com/rowingchenn/agent-ood-lab/blob/6f90b859f74f7527005b7fc7387335d5c9aeacb9/main.py)** to conduct experiments in a web environment with OOD inputs. 

- **Agent Selection**: Choose a pre-defined agent or specify a custom one using:  
  ```python
  agent_args = [AGENT]
  ```
- **BenchMark Setup**: Select webarena to set up OOD inputs in the web environment:
  ```python
  benchmark = "webarena"
  ```
   
## License

