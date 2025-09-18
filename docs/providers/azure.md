# Azure OpenAI configuration

> This guide shows how to run CAI against Azure-hosted OpenAI's models

## Prerequisites
- Azure subscription with **Azure OpenAI** access.
- A **deployed model** in Azure AI Portal (e.g., a deployment named `gpt-4o`).  
  See Microsoft docs on creating the resource & deploying models.  
  - [Create resource & deploy](https://learn.microsoft.com/azure/ai-foundry/openai/how-to/create-resource)
  - [Working with models](https://learn.microsoft.com/azure/ai-foundry/openai/how-to/working-with-models)

#### 1. Deploy the base model
In Azure AI Portal, go to **Deployments** and deploy the requested base model (e.g., gpt-4o).

#### 2. Get the deployment URL
From **Deployments**, select your deployment and copy the endpoint in this form: 

`https://<your-resource>.openai.azure.com/openai/deployments/<deployment-name>/chat/completions?api-version=2025-01-01-preview`

Set this value as `AZURE_API_BASE` in your `.env`.  
**Note:** CAI uses the OpenAI SDK style `base_url + /chat/completions`. For Azure, providing the full endpoint above (including `chat/completions?api-version=...`) ensures correct routing.

#### 3. Get your API key
From your Azure OpenAI resource home page (it is displayed on the resource home page, along with the subscription ID, resource name, etc.). Put it in `.env` as `AZURE_API_KEY`.

#### 4. Complete your `.env`
`OPENAI_API_KEY` must NOT be empty (use any placeholder like `"dummy"`). 

Example of good configured `.env`:

```bash
OPENAI_API_KEY="dummy"
AZURE_API_KEY="your_subscription_api_key"
AZURE_API_BASE="https://<your-resource>.openai.azure.com/openai/deployments/<deployment-name>/chat/completions?api-version=2025-01-01-preview"
# Optional (if your setup expects it):
# AZURE_API_VERSION="2025-01-01-preview"

ANTHROPIC_API_KEY=""
OLLAMA=""
PROMPT_TOOLKIT_NO_CPR=1
```

#### 5. Start CAI and select the model
Launch CAI and select the Azure model:

```vbnet
CAI> /model azure/<model-name>
╭─────────────────────────────────────────────────── Model Changed ────────────────────────────────────────────────────╮
│ Model changed to: azure/<model-name>                                                                               │
│ Note: This will take effect on the next agent interaction                                                                │
╰──────────────────────────────────────────────────────────────────────────────────────────────────────────────────────╯
```

From this point you are interacting with your Azure-hosted OpenAI model.

> ⚠️ Remember: you must select the model each time you start CAI.


> EXTRA configuration:
You can set the variable `CAI_MODEL` to avoid the need for repeated model setup during initialization.

```bash
CAI_MODEL=azure/<model-name-deployed>
```

## Troubleshooting

- 404 or “deployment not found”: Ensure you have correctly copied the URL of the deployed model.

Error example:
```sh
ERROR:cai.cli:Error in main loop: litellm.APIError: AzureException APIError - Resource not found
openai.NotFoundError: Error code: 404 - {'error': {'code': '404', 'message': 'Resource not found'}}
```

- 401: verify `AZURE_API_KEY` and that your region has access to the chosen model.

Error example:
```sh
ERROR:cai.cli:Error in main loop: litellm.AuthenticationError: AzureException AuthenticationError - Access denied due to invalid subscription key or wrong API endpoint. Make sure to provide a valid key for an active subscription and use a correct regional API endpoint for your resource.
openai.AuthenticationError: Error code: 401 - {'error': {'code': '401', 'message': 'Access denied due to invalid subscription key or wrong API endpoint. Make sure to provide a valid key for an active subscription and use a correct regional API endpoint for your resource.'}}
```

- Time-outs / rate limits: check Azure usage and quota.