# Step 1: User selects the guardrail provider id and type

```json
{
  "workflow_total_steps": 7,
  "step_number": 1,
  "provider_type": "bud",
  "provider_id": "4d1154b1-25c8-464b-a891-35e8bb1b1186"
}
```

# Step 2: User selects the required probes from the selected provider

```json
{
  "workflow_id": "c54e3bae-9f86-463d-be54-c334f7125e97",
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
  "workflow_id": "c54e3bae-9f86-463d-be54-c334f7125e97",
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

Above 2 steps are recursive and user could jump between them as required.

# Step 3: The guardrail models won't be onboarded initially so we need to show the selected models for deployment. This can be done using the model_uri field. This is required because some models like safeguard can have multiple policies (probes/rules) so we just collate and show distinct. For a project we only need to deploy one instance of each model and it should be manually or auto scaled therefore we will need to provide a status as well to show if any of the selected models is already running or need deployment.

```json
{
  "workflow_id": "c54e3bae-9f86-463d-be54-c334f7125e97",
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
  "derive_model_statuses": true
}
```

# Step 4: user will need to select available credentials similar to the model onboard flow. Since we've the model uri we could set the name, author name and tags in backend

```json
{
  "workflow_id": "c54e3bae-9f86-463d-be54-c334f7125e97",
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
  "derive_model_statuses": true,
  "credential_id": "a62f923a-deea-471d-bbed-4901dae52e11",
  "trigger_onboarding": true
}
```

# Step 6: User selects the hardware resource mode same as the one in model deployment workflow



# Step 7: User sets deployment specifications, this is similar to the model deployment workflow step but done for all the models to be deployed so each gets its own name and concurrency config
# Step 8: Once the specifications is done, we need to find the recommended clusters like in the model deployment workflow. Here the difference is that we might've multiple models rather than a single one,
so we need to run the recommendation for all models to be deployed and that too accounting for each predecessor to handle the edge case where individual recommendations show availability but when we deploy
we might only have resources for few bcz the calculation didn't account for other models. We use pipeline for triggering model deployments so, see if we can simply use the model deploy workflow itself. Here
since we've multiple models we need to only show clusters that can accomodate all the models to be deployed.
# Step 9: User selects deployment types, same as the is_standalone concept in the current guardrail deploy workflow
# Step 10: User selects projects
# Step 11: User selects endpoints if not is_standalone
# Step 12: User configure profile settings - name, description, guard_type, strictness level
# Step 13: The deployment progress, like in step 4 we might've multiple model deployments so we need to see how we can handle this with pipeline and enable notifications

We need to handle the cancel workflows for relevant steps and the entire workflow with full rollback.

bud pipeline sdk: https://github.com/BudEcosystem/BudAIFoundry-SDK.git
