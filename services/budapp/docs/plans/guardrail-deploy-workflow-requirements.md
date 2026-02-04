# Step 1: User selects the guardrail provider id and type

```json
{
  "workflow_total_steps": 11,
  "step_number": 1,
  "provider_type": "bud",
  "provider_id": "4d1154b1-25c8-464b-a891-35e8bb1b1186"
}
```

# Step 2: User selects the required probes from the selected provider

```json
{
  "workflow_id": "6a517e04-4a19-4d13-93aa-976c8130ece9",
  "step_number": 2,
  "provider_type": "bud",
  "provider_id": "4d1154b1-25c8-464b-a891-35e8bb1b1186",
  "probe_selections": [
    {"id": "0001de2e-c549-4ebb-ba74-039f895f0e7f"},
    {"id": "0e3ee4e9-99ff-4fea-b2f3-587a433adb45"},
    {"id": "3fc01a5a-850e-4673-ba37-ead25404cae2"},
    {"id": "7318db05-25c1-43fc-b6bd-cfeca4542b56"}
  ]
}
```

# Step 2 (cont): (Optional) User selects the rules for any of the selected probe if necessary

```json
{
  "workflow_id": "6a517e04-4a19-4d13-93aa-976c8130ece9",
  "step_number": 2,
  "provider_type": "bud",
  "provider_id": "4d1154b1-25c8-464b-a891-35e8bb1b1186",
  "probe_selections": [
    {
        "id": "0001de2e-c549-4ebb-ba74-039f895f0e7f",
        "rules": [
            {"id": "da8e9845-7b25-4a8e-a1d6-7699177b1e47", "status": "active"}
        ]
    },
    {"id": "0e3ee4e9-99ff-4fea-b2f3-587a433adb45"},
    {"id": "3fc01a5a-850e-4673-ba37-ead25404cae2"},
    {"id": "7318db05-25c1-43fc-b6bd-cfeca4542b56"}
  ]
}
```

Steps 2-3 are recursive and user could jump between them as required.

# Step 3: User selects project. This is required at this stage because module statuses need to be checked per project

```json
{
  "workflow_id": "6a517e04-4a19-4d13-93aa-976c8130ece9",
  "step_number": 3,
  "provider_type": "bud",
  "provider_id": "4d1154b1-25c8-464b-a891-35e8bb1b1186",
  "probe_selections": [
    {
        "id": "0001de2e-c549-4ebb-ba74-039f895f0e7f",
        "rules": [
            {"id": "da8e9845-7b25-4a8e-a1d6-7699177b1e47", "status": "active"}
        ]
    },
    {"id": "0e3ee4e9-99ff-4fea-b2f3-587a433adb45"},
    {"id": "3fc01a5a-850e-4673-ba37-ead25404cae2"},
    {"id": "7318db05-25c1-43fc-b6bd-cfeca4542b56"}
  ],
  "project_id": "9c3dba33-62df-461f-ad57-be49e191044e"
}
```

# Step 3 (cont): The guardrail models won't be onboarded initially so we need to show the selected models for deployment.

```json
{
  "workflow_id": "6a517e04-4a19-4d13-93aa-976c8130ece9",
  "step_number": 3,
  "provider_type": "bud",
  "provider_id": "4d1154b1-25c8-464b-a891-35e8bb1b1186",
  "probe_selections": [
    {
        "id": "0001de2e-c549-4ebb-ba74-039f895f0e7f",
        "rules": [
            {"id": "da8e9845-7b25-4a8e-a1d6-7699177b1e47", "status": "active"}
        ]
    },
    {"id": "0e3ee4e9-99ff-4fea-b2f3-587a433adb45"},
    {"id": "3fc01a5a-850e-4673-ba37-ead25404cae2"},
    {"id": "7318db05-25c1-43fc-b6bd-cfeca4542b56"}
  ],
  "project_id": "9c3dba33-62df-461f-ad57-be49e191044e"
}
```

# Step 4: user will need to select available credentials similar to the model onboard flow. Since we've the model uri we could set the name, author name and tags in backend

**Important:** Model statuses are only derived when BOTH `project_id` AND `probe_selections` are available. This ensures accurate status checks for the specific project.

```json
{
  "workflow_id": "6a517e04-4a19-4d13-93aa-976c8130ece9",
  "step_number": 4,
  "provider_type": "bud",
  "provider_id": "4d1154b1-25c8-464b-a891-35e8bb1b1186",
  "probe_selections": [
    {
        "id": "0001de2e-c549-4ebb-ba74-039f895f0e7f",
        "rules": [
            {"id": "da8e9845-7b25-4a8e-a1d6-7699177b1e47", "status": "active"}
        ]
    },
    {"id": "0e3ee4e9-99ff-4fea-b2f3-587a433adb45"},
    {"id": "3fc01a5a-850e-4673-ba37-ead25404cae2"},
    {"id": "7318db05-25c1-43fc-b6bd-cfeca4542b56"}
  ],
  "project_id": "9c3dba33-62df-461f-ad57-be49e191044e",
  "credential_id": "a62f923a-deea-471d-bbed-4901dae52e11"
}
```

# Step 5: User selects the hardware resource mode same as the one in model deployment workflow

```json
{
  "workflow_id": "6a517e04-4a19-4d13-93aa-976c8130ece9",
  "step_number": 5,
  "provider_type": "bud",
  "provider_id": "4d1154b1-25c8-464b-a891-35e8bb1b1186",
  "probe_selections": [
    {
        "id": "0001de2e-c549-4ebb-ba74-039f895f0e7f",
        "rules": [
            {"id": "da8e9845-7b25-4a8e-a1d6-7699177b1e47", "status": "active"}
        ]
    },
    {"id": "0e3ee4e9-99ff-4fea-b2f3-587a433adb45"},
    {"id": "3fc01a5a-850e-4673-ba37-ead25404cae2"},
    {"id": "7318db05-25c1-43fc-b6bd-cfeca4542b56"}
  ],
  "project_id": "9c3dba33-62df-461f-ad57-be49e191044e",
  "credential_id": "a62f923a-deea-471d-bbed-4901dae52e11",
  "hardware_mode": "shared"
}
```

# Step 6: User sets deployment specifications, this is similar to the model deployment workflow step but done for all the models to be deployed so each could get its own name and concurrency config or a shared one for all. Once done, cluster recommendation simulation will be run and results will be available from the workflow response

## Shared config for all models
```json
{
  "workflow_id": "6a517e04-4a19-4d13-93aa-976c8130ece9",
  "step_number": 6,
  "provider_type": "bud",
  "provider_id": "4d1154b1-25c8-464b-a891-35e8bb1b1186",
  "probe_selections": [
    {
        "id": "0001de2e-c549-4ebb-ba74-039f895f0e7f",
        "rules": [
            {"id": "da8e9845-7b25-4a8e-a1d6-7699177b1e47", "status": "active"}
        ]
    },
    {"id": "0e3ee4e9-99ff-4fea-b2f3-587a433adb45"},
    {"id": "3fc01a5a-850e-4673-ba37-ead25404cae2"},
    {"id": "7318db05-25c1-43fc-b6bd-cfeca4542b56"}
  ],
  "project_id": "9c3dba33-62df-461f-ad57-be49e191044e",
  "credential_id": "a62f923a-deea-471d-bbed-4901dae52e11",
  "hardware_mode": "shared",
  "deploy_config": {
    "input_tokens": 512,
    "output_tokens": 64,
    "concurrency": 1,
    "target_ttft": 50,
    "target_e2e_latency": 200
  }
}
```

## Per model config
```json
{
  "workflow_id": "6a517e04-4a19-4d13-93aa-976c8130ece9",
  "step_number": 6,
  "provider_type": "bud",
  "provider_id": "4d1154b1-25c8-464b-a891-35e8bb1b1186",
  "probe_selections": [
    {
        "id": "0001de2e-c549-4ebb-ba74-039f895f0e7f",
        "rules": [
            {"id": "da8e9845-7b25-4a8e-a1d6-7699177b1e47", "status": "active"}
        ]
    },
    {"id": "0e3ee4e9-99ff-4fea-b2f3-587a433adb45"},
    {"id": "3fc01a5a-850e-4673-ba37-ead25404cae2"},
    {"id": "7318db05-25c1-43fc-b6bd-cfeca4542b56"}
  ],
  "project_id": "9c3dba33-62df-461f-ad57-be49e191044e",
  "credential_id": "a62f923a-deea-471d-bbed-4901dae52e11",
  "hardware_mode": "shared",
  "per_model_deployment_configs": [
    {
        "model_id": "80a797b9-e7a6-42db-a259-0096926400f4",
        "deploy_config": {
          "input_tokens": 512,
          "output_tokens": 64,
          "concurrency": 1,
          "target_ttft": 50,
          "target_e2e_latency": 200
        }
    },
    {
        "model_id": "7cd66624-9e27-4f46-b7c8-0eaa58c83030",
        "deploy_config": {
          "input_tokens": 512,
          "output_tokens": 64,
          "concurrency": 5,
          "target_ttft": 50,
          "target_e2e_latency": 200
        }
    }
  ]
}
```

# Step 7: Once the recommendations are available users can select a single cluster for all models (based on recommendation) or select cluster per model

## Shared cluster for all models
```json
{
  "workflow_id": "6a517e04-4a19-4d13-93aa-976c8130ece9",
  "step_number": 7,
  "provider_type": "bud",
  "provider_id": "4d1154b1-25c8-464b-a891-35e8bb1b1186",
  "probe_selections": [
    {
        "id": "0001de2e-c549-4ebb-ba74-039f895f0e7f",
        "rules": [
            {"id": "da8e9845-7b25-4a8e-a1d6-7699177b1e47", "status": "active"}
        ]
    },
    {"id": "0e3ee4e9-99ff-4fea-b2f3-587a433adb45"},
    {"id": "3fc01a5a-850e-4673-ba37-ead25404cae2"},
    {"id": "7318db05-25c1-43fc-b6bd-cfeca4542b56"}
  ],
  "project_id": "9c3dba33-62df-461f-ad57-be49e191044e",
  "credential_id": "a62f923a-deea-471d-bbed-4901dae52e11",
  "hardware_mode": "shared",
  "deploy_config": {
    "input_tokens": 512,
    "output_tokens": 64,
    "concurrency": 1,
    "target_ttft": 50,
    "target_e2e_latency": 200
  },
  "cluster_id": "a17a94f7-6f4e-4c64-b31e-f9ff17323d56"
}
```

## Per model config
```json
{
  "workflow_id": "6a517e04-4a19-4d13-93aa-976c8130ece9",
  "step_number": 7,
  "provider_type": "bud",
  "provider_id": "4d1154b1-25c8-464b-a891-35e8bb1b1186",
  "probe_selections": [
    {
        "id": "0001de2e-c549-4ebb-ba74-039f895f0e7f",
        "rules": [
            {"id": "da8e9845-7b25-4a8e-a1d6-7699177b1e47", "status": "active"}
        ]
    },
    {"id": "0e3ee4e9-99ff-4fea-b2f3-587a433adb45"},
    {"id": "3fc01a5a-850e-4673-ba37-ead25404cae2"},
    {"id": "7318db05-25c1-43fc-b6bd-cfeca4542b56"}
  ],
  "project_id": "9c3dba33-62df-461f-ad57-be49e191044e",
  "credential_id": "a62f923a-deea-471d-bbed-4901dae52e11",
  "hardware_mode": "shared",
  "per_model_deployment_configs": [
    {
        "model_id": "80a797b9-e7a6-42db-a259-0096926400f4",
        "cluster_id": "a17a94f7-6f4e-4c64-b31e-f9ff17323d56",
        "deploy_config": {
          "input_tokens": 512,
          "output_tokens": 64,
          "concurrency": 1,
          "target_ttft": 50,
          "target_e2e_latency": 200
        }
    },
    {
        "model_id": "7cd66624-9e27-4f46-b7c8-0eaa58c83030",
        "cluster_id": "a17a94f7-6f4e-4c64-b31e-f9ff17323d56",
        "deploy_config": {
          "input_tokens": 512,
          "output_tokens": 64,
          "concurrency": 5,
          "target_ttft": 50,
          "target_e2e_latency": 200
        }
    }
  ]
}
```

# Step 8: User selects deployment types, same as the is_standalone concept in the current guardrail deploy workflow

```json
{
  "workflow_id": "6a517e04-4a19-4d13-93aa-976c8130ece9",
  "step_number": 8,
  "provider_type": "bud",
  "provider_id": "4d1154b1-25c8-464b-a891-35e8bb1b1186",
  "probe_selections": [
    {
        "id": "0001de2e-c549-4ebb-ba74-039f895f0e7f",
        "rules": [
            {"id": "da8e9845-7b25-4a8e-a1d6-7699177b1e47", "status": "active"}
        ]
    },
    {"id": "0e3ee4e9-99ff-4fea-b2f3-587a433adb45"},
    {"id": "3fc01a5a-850e-4673-ba37-ead25404cae2"},
    {"id": "7318db05-25c1-43fc-b6bd-cfeca4542b56"}
  ],
  "project_id": "9c3dba33-62df-461f-ad57-be49e191044e",
  "credential_id": "a62f923a-deea-471d-bbed-4901dae52e11",
  "hardware_mode": "shared",
  "deploy_config": {
    "input_tokens": 512,
    "output_tokens": 64,
    "concurrency": 1,
    "target_ttft": 50,
    "target_e2e_latency": 200
  },
  "cluster_id": "a17a94f7-6f4e-4c64-b31e-f9ff17323d56",
  "is_standalone": false
}
```

# Step 9: User selects endpoints if not is_standalone

```json
{
  "workflow_id": "6a517e04-4a19-4d13-93aa-976c8130ece9",
  "step_number": 9,
  "provider_type": "bud",
  "provider_id": "4d1154b1-25c8-464b-a891-35e8bb1b1186",
  "probe_selections": [
    {
        "id": "0001de2e-c549-4ebb-ba74-039f895f0e7f",
        "rules": [
            {"id": "da8e9845-7b25-4a8e-a1d6-7699177b1e47", "status": "active"}
        ]
    },
    {"id": "0e3ee4e9-99ff-4fea-b2f3-587a433adb45"},
    {"id": "3fc01a5a-850e-4673-ba37-ead25404cae2"},
    {"id": "7318db05-25c1-43fc-b6bd-cfeca4542b56"}
  ],
  "project_id": "9c3dba33-62df-461f-ad57-be49e191044e",
  "credential_id": "a62f923a-deea-471d-bbed-4901dae52e11",
  "hardware_mode": "shared",
  "deploy_config": {
    "input_tokens": 512,
    "output_tokens": 64,
    "concurrency": 1,
    "target_ttft": 50,
    "target_e2e_latency": 200
  },
  "cluster_id": "a17a94f7-6f4e-4c64-b31e-f9ff17323d56",
  "is_standalone": false,
  "endpoint_ids": [
    "f9dee4c5-084c-4f55-a8b8-ff16fcfa9388"
  ]
}
```

# Step 10: User configure profile settings - name, description, guard_type, strictness level

```json
{
  "workflow_id": "6a517e04-4a19-4d13-93aa-976c8130ece9",
  "step_number": 10,
  "provider_type": "bud",
  "provider_id": "4d1154b1-25c8-464b-a891-35e8bb1b1186",
  "probe_selections": [
    {
        "id": "0001de2e-c549-4ebb-ba74-039f895f0e7f",
        "rules": [
            {"id": "da8e9845-7b25-4a8e-a1d6-7699177b1e47", "status": "active"}
        ]
    },
    {"id": "0e3ee4e9-99ff-4fea-b2f3-587a433adb45"},
    {"id": "3fc01a5a-850e-4673-ba37-ead25404cae2"},
    {"id": "7318db05-25c1-43fc-b6bd-cfeca4542b56"}
  ],
  "project_id": "9c3dba33-62df-461f-ad57-be49e191044e",
  "credential_id": "a62f923a-deea-471d-bbed-4901dae52e11",
  "hardware_mode": "shared",
  "deploy_config": {
    "input_tokens": 512,
    "output_tokens": 64,
    "concurrency": 1,
    "target_ttft": 50,
    "target_e2e_latency": 200
  },
  "cluster_id": "a17a94f7-6f4e-4c64-b31e-f9ff17323d56",
  "is_standalone": false,
  "endpoint_ids": [
    "f9dee4c5-084c-4f55-a8b8-ff16fcfa9388"
  ],
  "name": "Test guardrail profile",
  "description": "A dummy profile",
  "guard_types": ["input", "output"],
  "severity_threshold": 0.5,
}
```

# Step 11: Trigger the deployment. Like in step 4 we might've multiple model deployments so we need to see how we can handle this with pipeline and enable notifications


```json
{
  "workflow_id": "6a517e04-4a19-4d13-93aa-976c8130ece9",
  "step_number": 11,
  "provider_type": "bud",
  "provider_id": "4d1154b1-25c8-464b-a891-35e8bb1b1186",
  "probe_selections": [
    {
        "id": "0001de2e-c549-4ebb-ba74-039f895f0e7f",
        "rules": [
            {"id": "da8e9845-7b25-4a8e-a1d6-7699177b1e47", "status": "active"}
        ]
    },
    {"id": "0e3ee4e9-99ff-4fea-b2f3-587a433adb45"},
    {"id": "3fc01a5a-850e-4673-ba37-ead25404cae2"},
    {"id": "7318db05-25c1-43fc-b6bd-cfeca4542b56"}
  ],
  "project_id": "9c3dba33-62df-461f-ad57-be49e191044e",
  "credential_id": "a62f923a-deea-471d-bbed-4901dae52e11",
  "hardware_mode": "shared",
  "deploy_config": {
    "input_tokens": 512,
    "output_tokens": 64,
    "concurrency": 1,
    "target_ttft": 50,
    "target_e2e_latency": 200
  },
  "cluster_id": "a17a94f7-6f4e-4c64-b31e-f9ff17323d56",
  "is_standalone": false,
  "endpoint_ids": [
    "f9dee4c5-084c-4f55-a8b8-ff16fcfa9388"
  ],
  "name": "Test guardrail profile",
  "description": "A dummy profile",
  "guard_types": ["input", "output"],
  "severity_threshold": 0.5,
  "trigger_workflow": true
}
```
