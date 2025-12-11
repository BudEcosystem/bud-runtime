import { AgentVariable } from "@/stores/useAgentStore";

interface PropertyDefinition {
  type: string;
  format?: string;
  title?: string;
}

interface SchemaDefinition {
  type: string;
  title: string;
  required: string[];
  properties: Record<string, PropertyDefinition>;
}

const mapDataTypeToJsonSchema = (dataType?: string): string => {
  switch (dataType) {
    case "number":
      return "integer";
    case "boolean":
      return "boolean";
    case "array":
      return "array";
    case "object":
      return "object";
    default:
      return "string";
  }
};

const buildPropertiesFromVariables = (
  variables: AgentVariable[],
): Record<string, PropertyDefinition> => {
  const properties: Record<string, PropertyDefinition> = {};

  variables.forEach((variable) => {
    // Skip variables with empty names
    if (!variable.name || !variable.name.trim()) {
      return;
    }

    const property: PropertyDefinition = {
      type: mapDataTypeToJsonSchema(variable.dataType),
      title: variable.description || variable.name,
    };

    // Add email format for email fields
    if (
      variable.validation?.includes("email") ||
      variable.name.toLowerCase().includes("email")
    ) {
      property.format = "email";
    }

    // Use the variable name as-is, even if it contains spaces
    // The API should handle property names with spaces
    properties[variable.name] = property;
  });

  return properties;
};

const buildRequiredFields = (variables: AgentVariable[]): string[] => {
  return variables
    .filter((variable) => variable.name && variable.name.trim())
    .map((variable) => variable.name);
};

const buildValidations = (
  variables: AgentVariable[],
  variableType: "input" | "output",
): Record<string, Record<string, string>> => {
  const validations: Record<string, Record<string, string>> = {};
  const typeKey = variableType === "input" ? "Input" : "Output"; // Use "Input"/"Output" to match $defs key

  validations[typeKey] = {};

  variables.forEach((variable) => {
    // Skip variables with empty names or no validation
    if (!variable.name || !variable.name.trim() || !variable.validation) {
      return;
    }

    // Use the validation string directly as the validation message (matching API sample)
    validations[typeKey][variable.name] = variable.validation;
  });

  return validations;
};

export const buildPromptSchemaPayload = (
  inputVariables: AgentVariable[],
  outputVariables: AgentVariable[],
  type: "input" | "output",
  deploymentName?: string,
  workflowId?: string,
  version: number = 1,
  setDefault: boolean = true,
  stepNumber: number = 1,
  workflowTotalSteps: number = 0,
  triggerWorkflow: boolean = false,
  promptId?: string,
) => {
  const variables = type === "input" ? inputVariables : outputVariables;
  const schemaTitle = type === "input" ? "InputSchema" : "OutputSchema";
  const defsKey = type === "input" ? "Input" : "Output"; // Key for $defs object

  // Build the schema definition
  const schemaDefinition: SchemaDefinition = {
    type: "object",
    title: schemaTitle,
    required: buildRequiredFields(variables),
    properties: buildPropertiesFromVariables(variables),
  };

  // Build the full schema with $defs (matching API sample structure)
  const schema = {
    $defs: {
      [defsKey]: schemaDefinition,
    },
    properties: {
      content: {
        $ref: `#/$defs/${defsKey}`,
      },
    },
    required: ["content"],
    title: schemaTitle,
    type: "object",
  };

  // Build validations
  const validations = buildValidations(variables, type);

  // Build the complete payload
  const payload: any = {
    step_number: stepNumber,
    workflow_total_steps: workflowTotalSteps,
    trigger_workflow: triggerWorkflow,
    version,
    set_default: setDefault,
    schema: {
      schema,
      validations,
    },
    type,
  };

  // Add optional fields if provided
  // Note: workflow_id is not sent for prompt-schema endpoint

  if (deploymentName) {
    payload.deployment_name = deploymentName;
  }

  if (promptId) {
    payload.prompt_id = promptId;
  }

  return payload;
};

export const buildPromptSchemaFromSession = (
  session: any,
  type: "input" | "output" = "output",
  stepNumber: number = 1,
  workflowTotalSteps: number = 0,
  triggerWorkflow: boolean = false,
) => {
  const deploymentName = session.selectedDeployment?.name;
  const workflowId = session.workflowId;
  const promptId = session.promptId;

  return buildPromptSchemaPayload(
    session.inputVariables || [],
    session.outputVariables || [],
    type,
    deploymentName,
    workflowId,
    1, // version
    true, // set_default
    stepNumber,
    workflowTotalSteps,
    triggerWorkflow,
    promptId,
  );
};
