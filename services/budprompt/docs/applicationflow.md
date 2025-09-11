# Existing Architecture

## Different Components in our application

### Deployments

- Deployment is a deployed llm model the user can access using a curl request, in the curl request user will specify the deployment name (model_name) and provide authorization token. the request will be send to BudGateway server.

- example for curl request to inference
```
curl --location 'http://20.66.97.208/v1/chat/completions' \
--header 'Content-Type: application/json' \
--header 'Authorization: Bearer <api_key>' \
--data '{
    "model": "qwen3-32b",
    "messages": [
        {
            "role": "user",
            "content": "Write a hello world program in python"
        }
    ]
}'
```

### Project

- Project is a collection of deployments.
- So user can create a project and deploy multiple models in a single project.
- Basically it is a grouping of deployments.
- User can create api key for a project. so this api key will be used to authenticate the user when they are using the deployments in the project.


## Microservices

- BudGateway
- BudApp
- BudPrompt

### BudGateway

- BudGateway is a server that will be used to route the requests to the deployments.
- It will be responsible for authenticating the user and routing the requests to the deployments.
    - From the api key it will identify the project
    - it will route the request to the deployment where user will have the specified deployment name in the request body.

### BudApp

- BudApp is a web application that will be used to create and manage the projects and deployments.
- It will be responsible for creating the projects and deployments.
- It will be responsible for managing the projects and deployments.
- It will be responsible for creating and managing prompts **IMPORTANT**
- Basically it is application layer for frontend to communicate with backend and it will communicate with all other microservices.
- It will be responsible for creating and managing api keys for projects.

### BudPrompt
- It will be responsible for executing the prompts and returning the response to the user.


# Prompts

## Overview

User can able to create prompts. within a project. So the user can able to choose which Deployment of the project to use for the prompt.

## Prompt Flow

THere are two flows for creating prompts.

### Flow 1

- User Navigate to the project
- Click Create Deployment Button
- User choose model or prompt going to deploy
- User can create a new prompt or use existing prompt
- Consider user choose to create a new prompt
  - User will be redirected to the prompt creation page
  - There are different types of prompts but for now we will have only one type of prompt which is Simple Prompt user choose single prompt and rest of the types will be added later.
  - User will be able to try a new prompt with the following fields:
    - There will be an option to choose the deployment from the project.
    - Define the model params for the deployment. (temperature, max_tokens, top_p, frequency_penalty, presence_penalty, stop_sequences, etc)
    - User can add tools which will be different integrations like slack, notion etc.. similar to the tools defining in openai prompts
      - There will be a list of tools which will be available to the user.
      - User can activate and deactivate the tools
      - While connecting the tool user need to provide access keys for the tools.
    - User can choose the prompt version from the list of versions.
      - This will call the api to get prompt details of that particular version.
    - User can choose the input is a structured or not
      - if it is not structured user can provide the input in the text area (it will be a string input)
      - if it is structured user can provide the input in the structured format.
        - Define variable name
        - Define variable type
        - Define variable description
        - Define default value
        - Enable validation or not
          - Enabling validation will be two types
            - Basic Validation
              - User can provide basic validation supported by the pydantic library
            - Custom Validation
              - Using llm the user can create a pydantic validation

      - System Prompt (supported jinja template)
      - Set list of messages with different roles which will be used to keep message context
        - User (support jinja template)
        - Assistant (support jinja template)
        - Developer (support jinja template)
        - Tools
      - User can choose the output is a structured or not
      - if it is not structured user can provide the output in the text area (it will be a string output)
      - if it is structured user can provide the output in the structured format.
        - Define variable name
        - Define variable type
        - Define variable description
        - Define default value
        - Enable validation or not
          - Enabling validation will be two types
            - Basic Validation
              - User can provide basic validation supported by the pydantic library
            - Custom Validation
              - Using llm the user can create a pydantic validation
      - Allow multiple calls boolean(turn on or off)
        - if it is true there will be multiple internal llm calls will taken to get the output
        - if it is false there will be single llm call to get the output
      - There will a button to compare different prompts (a plus icon)
        - When user click the button it will create a new prompt in the same display so user can able to compare with different prompts in a single window
        - Basically a multiple window will be created in frontend with fixed width so user can create different prompts and see how the output is changing in individual execution
  - If user choose to use existing prompt these content will be pre-filled in the form as it is existing in the prompt
  - User can able to save the prompt
  - User can able to Run the prompt
    - Clicking run will transform the user defined input to a sequential type form inputs (it is in comparable multiple window as how many compare window user created)
    - Example:
    - User defined input:
          [a string, a boolean, a enum(option1, option2, option3)]
    - Frontend will display the form with iterative inputs in sequential order.
        - User first see a string input
        - User can able to enter the string input
        - User can able to click next button
        - User see a switch input
        - User can able to click next button
        - User see a dropdown input
        - User can able to select the dropdown option
        - User can able to click submit button
        - Basically user can able to interact how the prompt is getting working when it is deployed.
  - After that user will be transform to the UI where user can able to execute the prompt (it is in comparable multiple window as how many compare window user created)
  - User can define the minimum concurrency, maximum concurrency, enable or disable auto scale, enable or disable caching, enable or disable rate limiting
  - Successfully Created prompt

### Flow 2
  - Instead of going to a project, user can able to deploy a prompt directly from the home page from the navbar
  - On this way, user will pick one prompt from the list of prompts
  - User can select a project from the list of projects
  - User can able to create a new prompt by following the same flow as flow 1
  (Here since we are not going to a project, we will have an extra step to select the project. this is the only difference between flow 1 and flow 2)


## Technical Architecture

## Create a prompt
- In BudApp,
  - There will be an api to create a prompt
  - This will create a json structure of the prompt and save in the dapr state store by specifying a key as prompt id.
  - The meta information to list in the frontend will be save in the budapp database.
  - The prompt id will be used to identify the prompt in the dapr state store.

## List of prompts
- In BudApp,
  - There will be an api to list the prompts
  - The meta information to list in the frontend will be save in the budapp database.

## Get a prompt
- In BudApp,
    - There will be an api to get a prompt details
    - Get the prompt details from the dapr state store.

## Update a prompt
- In BudApp,
    - There will be an api to update a prompt
    - Meta information will be updated in the budapp database.
    - Update the prompt details in the dapr state store.

## Delete a prompt
- In BudApp,
    - There will be an api to delete a prompt
    - Delete the prompt details from the dapr state store.

# Run a prompt
- In BudApp, there will be an api to run a prompt
    - This will pass the json and input will return the output

## Executing a prompt
- The curl will be send to the BudGateway server
- it uses v1/responses endpoint.
- Since it is a prompt the gateway will call the BudPrompt microservice
- From the prompt id it will get the prompt details from the dapr state store.
- It will execute the prompt and return the output
- The output will be returned to the user
