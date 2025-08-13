import EditCluster from "./Cluster/EditCluster";
import DeployClusterStatus from "src/flows/DeployClusterStatus";
import CreateClusterStatus from "src/flows/CreateClusterStatus";
import ExtractingModel from "src/flows/AddModel/Local/ExtractingModelStatus";
import DeployModelStatus from "src/flows/DeployModelStatus";
import SecurityScanStatus from "src/flows/AddModel/Local/SecurityScanStatus";
import CreateProjectSuccess from "src/flows/CreateProjectSuccess";
import DeployModel from "src/flows/DeployModel";
import DeployModelChooseCluster from "src/flows/DeployModelChooseCluster";
import DeployModelSpecification from "src/flows/DeployModelSpecification";
import DeployModelTemplate from "src/flows/DeployModelTemplate";
import DeployModelCredentialSelect from "src/flows/DeployModel/DeployModelCredentialSelect";
import InviteMembers from "src/flows/InviteMembers";
import NewProject from "src/flows/NewProject";
import ModelSource from "src/flows/AddModel/ModelSource";
import ModelCloudProviders from "src/flows/AddModel/Cloud/CloudProviders";
import ModelList from "src/flows/AddModel/Cloud/ModelList";
import AddModel from "src/flows/AddModel/Cloud/AddModel";
import ModelEvaluations from "src/flows/AddModel/Cloud/SelectModelEvaluations";
import SelectModelEvaluations from "src/flows/RunModelEvaluations/SelectModelEvaluations";
import CreateClusterSuccess from "src/flows/CreateClusterSuccess";
import ModelSuccessCard from "src/flows/AddModel/Cloud/ModelSuccess";
import SelectClusterEvaluations from "src/flows/RunModelEvaluations/selectClusterEvaluations";
import SelectCredentials from "src/flows/RunModelEvaluations/SelectCredentials";
import EvaluationInformation from "src/flows/RunModelEvaluations/EvaluationInformation";
import EvaluationResults from "src/flows/RunModelEvaluations/EvaluationResults";
import RunModelSuccess from "src/flows/RunModelEvaluations/RunModelSuccess";
import StopWarning from "src/flows/RunModelEvaluations/StopWarning";
import EditModel from "src/flows/EditModel/EditModel";
import AddLocalModel from "src/flows/AddModel/Local/AddLocalModel";
import AddingModelToRepo from "src/flows/AddModel/Local/AddingModelToRepo";
import SelectOrAddCredentials from "src/flows/AddModel/Local/SelectOrAddCredentials";
import ScanCompleted from "src/flows/AddModel/Local/ScanCompleted";
import AddCluster from "src/flows/Cluster/AddCluster";
import AddWorker from "src/flows/Worker/AddWorker";
import ViewModel from "src/flows/ViewModel/ViewModelDetails";
import EditProject from "src/flows/Project/EditProject";
import AddMembers from "src/flows/Project/AddMembers";
import WorkerDetails from "src/flows/Worker/WorkerDetails";
import UseModel from "src/flows/Project/UseModel";
import DeleteCluster from "src/flows/Cluster/DeleteCluster";
import DeployModelSuccess from "src/flows/DeployModel/DeployModelSuccess";
import ClusterDeleteStatus from "./Cluster/ClusterDeleteStatus";
import EndpointDeleteStatus from "./DeployModel/EndpointDeleteStatus";
import AddCredentialsChooseProvider from "./Credentials/AddCredentials/AddCredentialsChooseProvider";
import AddCredentialForm from "./Credentials/AddCredentials/AddCredentialForm";
import ViewCredential from "./Credentials/ViewCredentials";
import CredentialsSuccessCard from "./Credentials/AddCredentials/CredentialsSuccess";
import ViewProjectCredential from "./Credentials/_project/ViewCredentials";
import AddNewKey from "./Credentials/_project/AddNewKey";
import EditProjectCredential from "./Credentials/_project/editProjectCredential";
import LicenseDetails from "./LicenseDetails";
import DerivedModelList from "@/components/ui/bud/models/DerivedModelList";
import ClusterEvent from "./Cluster/Event";
import AddWorkerClusterConfiguration from "./Worker/AddWorkerClusterConfiguration";
import AddWorkerSuccess from "./Worker/AddWorkerSuccess";
import AddWorkerConfigStatus from "./Worker/AddWorkerConfigStatus";
import AddWorkerDeployStatus from "./Worker/AddWorkerDeployStatus";
import WorkerDeleteStatus from "./Worker/WorkerDeleteStatus";
import ViewUser from "./user/ViewUser";
import EditUser from "./user/EditUser";
import ResetPassword from "./user/ResetPassword";
import AddUser from "./user/AddUser";
import AddUserDetails from "./user/AddUserDetails";
import AddBenchmark from "./Benchmark/AddBenchmark";
import Datasets from "./Benchmark/Datasets";
import Configuration from "./Benchmark/Configuration";
import SelectCluster from "./Benchmark/SelectCluster";
import SelectNodes from "./Benchmark/SelectNodes";
import SelectModel from "./Benchmark/SelectModel";
import BenchmarkConfiguration from "./Benchmark/BenchmarkConfiguration";
import SimulateRun from "./Benchmark/SimulateRun";
import BenchmarkingProgress from "./Benchmark/BenchmarkingProgress";
import BenchmarkingFinished from "./Benchmark/BenchmarkingFinished";
import CloudProvidersListing from "./Credentials/_cloud/CloudProvidersListing";
import AddCloudCredentialForm from "./Credentials/_cloud/AddCloudCredentialForm";
import CloudCredentialsSuccess from "./Credentials/_cloud/CloudCredentialsSuccess";
import ChooseCloudSource from "./Cluster/ChooseCloudSource";
import CloudChooser from "./Cluster/CloudChooser";
import ChooseCloudCredentialStep from "./Cluster/_cloud/ChooseCloudCredential";
import ConfigureClusterDetails from "./Cluster/_cloud/ConfigureClusterDetails";
import QuantizationDetail from './Quantization/QuantizationDetail';
import QuantizationMethod from './Quantization/QuantizationMethod';
import AdvancedSettings from './Quantization/AdvancedSettings';
import SimulationStatus from './Quantization/SimulationStatus';
import QuantizationSelectCluster from './Quantization/SelectCluster';
import QuantizationResult from './Quantization/QuantizationResult';
import DeploymentStatus from './Quantization/DeploymentStatus';
import SelectEvaluationType from "./runSimulation/SelectType";
import SelectUseCase from "./runSimulation/SelectUseCase";
import AdditionalSettings from "./runSimulation/AdditionalSettings";
import SelectModelForEvaluation from "./runSimulation/SelectModel";
import ModelQuantisation from "./runSimulation/ModelQuantisation";
import SelectHardware from "./runSimulation/SelectHardware";
import HardwareSpecifications from "./runSimulation/HardwareSpecifications";
import SimulationDetails from "./runSimulation/SimulationDetails";
import { SelectAdapterModel } from "./AddAdapter/SelectAdapterModel";
import { AdapterDetail } from "./AddAdapter/AdapterDetail";
import { AdapterStatus } from "./AddAdapter/AdapterStatus";
import { AdapterResult } from "./AddAdapter/AdapterResult";
import AddBenchmarkCredentialSelect from "./Benchmark/AddBenchmarkCredentialSelect";
import ChooseModality from "./AddModel/ChooseModality";
import DeployModelAutoScale from "./DeployModel/DeployModelAutoScale";
import EditProfile from "./settings/EditProfile";
import CreateRoute from "./Routes/CreateRoute";
import SelectEndpointsForRoutes from "./Routes/SelectEndpointsForRoutes";
import SelectFallbackDeployment from "./DeployModel/SelectFallbackDeployment";
import NewExperimentDrawer from "./Evaluations/NewExperiment";
import NewEvaluation from "./Evaluations/RunEvaluation/NewEvaluation";
import SelectModelForNewEvaluation from "./Evaluations/RunEvaluation/SelectModel";
import SelectTrait from "./Evaluations/RunEvaluation/SelectTrait";
import SelectEvaluation from "./Evaluations/RunEvaluation/SelectEvaluation";
import EvaluationSummary from "./Evaluations/RunEvaluation/EvaluationSummary";
import NewExperimentSuccess from "./Evaluations/NewExperiment/newExperimentSuccess";
import Publish from "./Project/Publish";
import ViewEvalDetailscopy from "./Evaluations/RunEvaluation/ViewEvalDetail";

export const StepComponents = {
  "new-project": NewProject,
  "invite-members": InviteMembers,
  "project-success": CreateProjectSuccess,
  "invite-success": CreateProjectSuccess,
  "deploy-model": DeployModel,
  "deploy-model-credential-select": DeployModelCredentialSelect,
  "deploy-model-template": DeployModelTemplate,
  "deploy-model-specification": DeployModelSpecification,
  "deploy-cluster-status": DeployClusterStatus,
  "deploy-model-choose-cluster": DeployModelChooseCluster,
  "deploy-model-auto-scaling": DeployModelAutoScale,
  "deploy-model-status": DeployModelStatus,
  "model-source": ModelSource,
  "modality-source": ChooseModality,
  "model-list": ModelList,
  "add-model": AddModel,
  "model-evaluations": ModelEvaluations,
  "select-model-evaluations": SelectModelEvaluations,
  "model-success": ModelSuccessCard,
  "select-cluster-evaluations": SelectClusterEvaluations,
  "select-credentials": SelectCredentials,
  "evaluation-information": EvaluationInformation,
  "evaluation-results": EvaluationResults,
  "run-model-success": RunModelSuccess,
  "stop-warning": StopWarning,
  "edit-model": EditModel,
  "view-message-model": CreateProjectSuccess,
  "view-message-cluster": CreateProjectSuccess,
  "add-local-model": AddLocalModel,
  "extracting-model": ExtractingModel,
  "adding-model-to-repo": AddingModelToRepo,
  "select-or-add-credentials": SelectOrAddCredentials,
  "security-scan-status": SecurityScanStatus,
  "scan-completed": ScanCompleted,
  "model-scan-completed": ScanCompleted,
  "cloud-providers": ModelCloudProviders,
  "add-cluster": AddCluster,
  "edit-cluster": EditCluster,
  "view-model-details": ViewModel,
  "create-cluster-status": CreateClusterStatus,
  "create-cluster-success": CreateClusterSuccess,
  "edit-project": EditProject,
  "add-worker": AddWorker,
  "add-worker-cluster-config-status": AddWorkerConfigStatus,
  "add-worker-cluster-configuration": AddWorkerClusterConfiguration,
  "add-worker-deploy-status": AddWorkerDeployStatus,
  "add-worker-success": AddWorkerSuccess,
  // "edit-project": EditProject,
  "add-members": AddMembers,
  "worker-details": WorkerDetails,
  "use-model": UseModel,
  "publish": Publish,
  "delete-cluster": DeleteCluster,
  "deploy-model-success": DeployModelSuccess,
  "delete-cluster-status": ClusterDeleteStatus,
  "delete-endpoint-status": EndpointDeleteStatus,
  "add-credentials-choose-provider": AddCredentialsChooseProvider,
  "add-credentials-form": AddCredentialForm,
  "view-credentials": ViewCredential,
  "credentials-success": CredentialsSuccessCard,
  "view-project-credentials": ViewProjectCredential,
  "add-new-key": AddNewKey,
  "edit-project-credential": EditProjectCredential,
  "license-Details": LicenseDetails,
  "derived-model-list": DerivedModelList,
  "cluster-event": ClusterEvent,
  "delete-worker-status": WorkerDeleteStatus,
  "view-user": ViewUser,
  "edit-user": EditUser,
  "reset-password": ResetPassword,
  "add-user": AddUser,
  "add-user-details": AddUserDetails,
  "model_benchmark": AddBenchmark,
  "Datasets": Datasets,
  "Configuration": Configuration,
  "Select-Cluster": SelectCluster,
  "Select-Nodes": SelectNodes,
  "Select-Model": SelectModel,
  "model_benchmark-credential-select": AddBenchmarkCredentialSelect,
  "Benchmark-Configuration": BenchmarkConfiguration,
  "simulate-run": SimulateRun,
  "Benchmarking-Progress": BenchmarkingProgress,
  "Benchmarking-Finished": BenchmarkingFinished,
  // Clouds & Cloud Credentials
  "add-new-cloud-provider": CloudProvidersListing,
  "add-cloud-credential-form": AddCloudCredentialForm,
  "cloud-credentials-success": CloudCredentialsSuccess,
  "add-cluster-select-source": ChooseCloudSource,
  "add-cluster-select-provider": CloudChooser,
  "choose-cloud-credential": ChooseCloudCredentialStep,
  "configure-cluster-details": ConfigureClusterDetails,
  'quantization-detail': QuantizationDetail,
  'quantization-method': QuantizationMethod,
  'advanced-settings': AdvancedSettings,
  'quantization-simulation-status': SimulationStatus,
  'quantization-select-cluster': QuantizationSelectCluster,
  'quantization-deployment-status': DeploymentStatus,
  'quantization-result': QuantizationResult,
  "select-evaluation-type": SelectEvaluationType,
  "select-use-case": SelectUseCase,
  "additional-settings": AdditionalSettings,
  "select-model-for-evaluation": SelectModelForEvaluation,
  "model-quantisation": ModelQuantisation,
  "select-hardware": SelectHardware,
  "hardware-pecifications": HardwareSpecifications,
  "simulation-details": SimulationDetails,
  "add-adapter-select-model": SelectAdapterModel,
  "add-adapter-detail": AdapterDetail,
  "add-adapter-status": AdapterStatus,
  "add-adapter-result": AdapterResult,
  "edit-user-profile": EditProfile,
  // routes
  "create-route-data": CreateRoute,
  "select-endpoints-route": SelectEndpointsForRoutes,
  // deployment selection
  "select-fallback-deployment": SelectFallbackDeployment,
  // experiments
  "new-experiment": NewExperimentDrawer,
  "new-experiment-success": NewExperimentSuccess,
  // new evaluations
  "new-evaluation": NewEvaluation,
  "select-model-new-evaluation": SelectModelForNewEvaluation,
  "select-traits": SelectTrait,
  "select-evaluation": SelectEvaluation,
  // "view-eval-details": ViewEvalDetails,
  "view-eval-details": ViewEvalDetailscopy,
  "evaluation-summary": EvaluationSummary,

};

export type StepComponentsType = keyof typeof StepComponents;
