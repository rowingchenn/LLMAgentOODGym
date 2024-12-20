# LLMAgentOODGym
OOD benchmark study for LLM agents based on BrowserGym and AgentLab.

Built on the [AgentLab](https://github.com/ServiceNow/AgentLab) and [BrowserGym](https://github.com/ServiceNow/BrowserGym) repositories.

Submodules:
- [OODAgentLab](https://github.com/rowingchenn/agent-ood-lab)
- [OODBrowserGym](https://github.com/rowingchenn/agent-ood-gym)

Arthor: Weichen Zhang

Email: rowingchenn@berkeley.edu

Coorperator: Sirui Li, Mengqi Zou, Yiming Zhang, Shujie Deng, Xinran Fang

## Prerequisites

Make sure you have the following installed:
- [Git](https://git-scm.com/downloads)
- [Conda](https://docs.conda.io/projects/conda/en/latest/user-guide/install/index.html)

## Clone the Main Repository and Initialize Submodules

To clone the main repository along with its submodules, use:

```bash
git clone --recursive git@github.com:rowingchenn/LLMAgentOODGym.git
cd LLMAgentOODGym
```

If you have already cloned the main repository without submodules, you can initialize and update submodules manually with:

```bash
git submodule update --init --recursive
```

## Setting up the Environment

### 1. Create a New Conda Environment

To set up the environment, first create a new Conda environment. Run the following command:

```bash
conda create -n oodgym python=3.12.7
conda activate <environment_name>
```

### 2. Install Dependencies for Each Subproject

This project consists of two subprojects (`BrowserGym` and `AgentLab`). You need to install each subproject in editable mode to ensure that any local code changes are reflected immediately. Make sure you install agent_ood_lab first and then install agent_ood_gym!

#### 2.1 Install AgentLab

**Navigate to the AgentLab directory** and install it in editable mode:

   ```bash
   cd agent_ood_lab
   pip install -e .
   ```

#### 2.2 Install BrowserGym

**Navigate to the BrowserGym directory** and install it in editable mode:

   ```bash
   cd agent_ood_gym
   make install
   ```

#### 2.3 Install WorkArena[following work]

**Navigate to the WorkArena directory** and install it in editable mode:

   ```bash
   cd agent_ood_gym/agent_ood_gym/work_arena
   pip install -e .
   ```

You don't need to run workarena-install since the instance of ServiceNow has already set up. You can access the instance by setting the SNOW_INSTANCE_URL, SNOW_INSTANCE_UNAME and SNOW_INSTANCE_PWD environment variables below.

#### 3.4 Install EmbodiedGym

   ```bash
   pip install alfworld[full]
   ```
   Download PDDL & Game files and pre-trained MaskRCNN detector:

   ```bash
   export ALFWORLD_DATA=<path to: agent_ood_gym/embodiedgym/alfworld/data>
   alfworld-download
   ```

### 3. Configure Environment Variables

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

   # WorkArena config[following work]
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

   # EmbodiedGym config
   export ALFWORLD_DATA=<path to: agent_ood_gym/embodiedgym/alfworld/data>
   ```

3. **Apply the changes** by running:

   ```bash
   source ~/.bashrc
   ```

This ensures all required environment variables are set every time you start a new terminal session.

## Run the Experiments
### EmbodiedGym
We currently only integrated Alfworld into the environment. To run the experiments, you can run this script: [LLMAgentOODGym/agent_ood_lab/src/agentlab/agents/testing_agent/test_embodied_ood_magic.py](https://github.com/rowingchenn/agent-ood-lab/blob/main/src/agentlab/agents/testing_agent/test_embodied_ood_magic.py)

And the results will be saved in the `AGENTLAB_EXP_ROOT` folder.

### BrowserGym
We currently only integrated WebArena into the environment. To run the experiments, you can run this script: [LLMAgentOODGym/agent_ood_lab/src/agentlab/main.py](https://github.com/rowingchenn/agent-ood-lab/blob/main/main.py)


### Configure your own LLM agents
You can configure your own LLM agents by modifying the [agent_ood_lab/src/agentlab/agents/generic_agent/agent_configs.py](https://github.com/rowingchenn/agent-ood-lab/blob/main/src/agentlab/agents/generic_agent/agent_configs.py) file.

Read the [AgentLab documentation](https://github.com/ServiceNow/AgentLab) for more information.
   
## License

