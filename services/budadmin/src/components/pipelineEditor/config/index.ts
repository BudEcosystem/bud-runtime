/**
 * Workflow Configuration
 *
 * Configuration and registries for the workflow editor.
 */

export {
  actionCategories,
  allActions,
  getActionMeta,
  getActionParams,
  getRequiredParams,
  getOptionalParams,
  validateParams,
  getDefaultParams,
  DEFAULT_ACTION_META,
} from './actionRegistry';
export type {
  ActionMeta,
  ActionCategory,
  ParamDefinition,
  ParamType,
  SelectOption,
} from './actionRegistry';

export {
  pipelineNodeTypes,
  DEFAULT_NODE_TYPE,
  SPECIAL_NODE_TYPES,
  UNDELETABLE_NODE_TYPES,
  UNCOPYABLE_NODE_TYPES,
} from './pipelineNodeTypes';

export {
  pipelineValidationRules,
  validatePipeline,
  startNodeRule,
  uniqueStepIdsRule,
  validDependenciesRule,
  connectedNodesRule,
  startNodeConnectedRule,
  conditionalNodeRule,
} from './pipelineValidation';
