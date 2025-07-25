import random
from collections import deque
from dataclasses import dataclass
from functools import partial
from typing import Any, Deque, Dict, List, Optional, Tuple

import numpy as np
from budmicroframe.commons import logging
from deap import base, creator, gp, tools
from tqdm import tqdm

from ..engine_ops import check_config_compatibility, get_engine_properties
from ..model_ops.analysis import ModelAnalysis
from .hardware import CostCalculator
from .regressor import BenchmarkPredictor


logger = logging.get_logger(__name__)


@dataclass
class EvaluationResult:
    config: Dict[str, Any]
    kv_cache_memory: float
    ttft: float
    e2e_latency: float
    throughput_per_user: float
    concurrency: int
    fitness: Tuple[float, float, float]
    error_rate: float
    cost_per_million_tokens: float


class Evolution:
    def __init__(
        self,
        model: str,
        input_tokens: int,
        output_tokens: int,
        max_concurrency: int,
        target_ttft: float,
        target_throughput_per_user: float,
        target_e2e_latency: float,
        device_config: Dict[str, Any],
        generation: int,
        population_size: int,
        engine_name: str,
        dtype: Optional[str] = None,
        benchmark_predictor_models_dir: Optional[str] = None,
        elite_ratio: float = 0.2,
        top_k: int = 5,
        error_threshold: float = 0.01,
        convergence_generations: int = 10,
    ):
        """Initialize the Evolution class.

        Args:
            model (str): The name of the model.
            input_tokens (int): The number of input tokens.
            output_tokens (int): The number of output tokens.
            concurrency (int): The concurrency level.
            target_e2e_latency (float): The target end to end latency.
            target_ttft (float): The target time-to-first-token.
            target_throughput_per_user (float): The target throughput per user.
            device_config (Dict[str, Any]): The device configuration.
            generation (int): The number of generations.
            population_size (int): The size of the population.
            engine_name (str): The name of the engine.
            benchmark_predictor_model_path (str): The path to the benchmark predictor model.
            elite_ratio (float, optional): The ratio of elite individuals to preserve. Defaults to 0.2.
            top_k (int, optional): The number of top individuals to be returned. Defaults to 5.
            error_threshold (float, optional): The error threshold. Defaults to 0.01.
            convergence_generations (int, optional): The number of generations to wait for convergence. Defaults to 10.
        """
        self.model = model
        self.input_tokens = input_tokens
        self.output_tokens = output_tokens
        self.max_concurrency = max_concurrency
        self.target_e2e_latency = target_e2e_latency
        self.target_ttft = target_ttft
        self.target_throughput_per_user = target_throughput_per_user
        self.device_config = device_config
        self.generation = generation
        self.population_size = population_size
        self.engine_name = engine_name
        self.dtype = dtype
        self.elite_ratio = elite_ratio
        self.top_k = top_k
        self.convergence_generations = convergence_generations
        self.error_threshold = error_threshold

        self.engine_config = get_engine_properties(self.engine_name, {"model": self.model})
        self.optimizer_params = self._get_optimizer_params()

        self.benchmark_predictor = BenchmarkPredictor(
            self.engine_name, self.device_config["type"], benchmark_predictor_models_dir
        )
        self.cost_calculator = CostCalculator()

        self._init_boundaries()
        self._initialize_deap()

        self.evaluated_configs: Dict[Tuple[Any, ...], Optional[EvaluationResult]] = {}
        self.top_configs: Deque[EvaluationResult] = deque(maxlen=self.top_k)
        self.generations_since_improvement = 0

    def _init_boundaries(self) -> None:
        # TODO: Use TP based on the evolution
        model_analysis = ModelAnalysis(
            model=self.model,
            device_config=self.device_config.copy(),
            input_tokens=self.input_tokens,
            output_tokens=self.output_tokens,
            concurrency=1,
            tp_size=1,
        )
        max_concurrency = model_analysis.get_max_concurrency(self.device_config["mem_per_GPU_in_GB"])
        self.max_concurrency = min(max_concurrency, self.max_concurrency)

    def _get_optimizer_params(self) -> Dict[str, Any]:
        engine_config_dict = dict(self.engine_config.items())
        engine_config_dict["tensor_parallel_size"] = partial(
            engine_config_dict["tensor_parallel_size"],
            min_val=1,
            max_val=self.device_config["available_count"],
        )
        engine_config_dict["concurrency"] = partial(self.get_concurrency, self.max_concurrency)
        logger.info(f"Evolution Dtype: {self.dtype}")
        if self.dtype is None:
            engine_config_dict.pop("quantization", None)
        return engine_config_dict

    def _initialize_deap(self) -> None:
        creator.create(
            "FitnessMulti", base.Fitness, weights=(-1.0, 1.0, -1.0)
        )  # performance, concurrency, cost_per_million_tokens_per_hour
        creator.create("Individual", list, fitness=creator.FitnessMulti)

        self.toolbox = base.Toolbox()

        for param in self.optimizer_params:
            logger.info(f"Registering {param}")
            self.toolbox.register(f"{param}", self.optimizer_params[param])

        self.toolbox.register(
            "individual",
            tools.initCycle,
            creator.Individual,
            [getattr(self.toolbox, param) for param in self.optimizer_params],
            n=1,
        )
        self.toolbox.register("population", tools.initRepeat, list, self.toolbox.individual)

        # Genetic operators
        self.toolbox.register("evaluate", self._evaluate_func)
        self.toolbox.register("mate", self._mate_func)
        self.toolbox.register("select", tools.selNSGA2)

    def _individual_to_config(self, individual: List[Any]) -> Dict[str, Any]:
        return {param: individual[idx] for idx, param in enumerate(self.optimizer_params)}

    def _config_to_tuple(self, config: Dict[str, Any]) -> Tuple[Any, ...]:
        return tuple(config[param] for param in sorted(self.optimizer_params))

    def _mate_func(self, ind1: List[Any], ind2: List[Any]) -> Tuple[List[Any], List[Any]]:
        # child1, child2 = tools.cxTwoPoint(ind1, ind2)
        child1, child2 = tools.cxBlend(ind1, ind2, alpha=0.5)
        return child1, child2

    def _pick_two_individuals_eligible_for_crossover(
        self, population: List[Any]
    ) -> Tuple[Optional[List[Any]], Optional[List[Any]]]:
        primitives_by_ind = [{node.name for node in ind if isinstance(node, gp.Primitive)} for ind in population]
        pop_as_str = [str(ind) for ind in population]

        eligible_pairs = [
            (i, i + 1 + j)
            for i, ind1_prims in enumerate(primitives_by_ind)
            for j, ind2_prims in enumerate(primitives_by_ind[i + 1 :])
            if not ind1_prims.isdisjoint(ind2_prims) and pop_as_str[i] != pop_as_str[i + 1 + j]
        ]

        # Pairs are eligible in both orders, this ensures that both orders are considered
        eligible_pairs += [(j, i) for (i, j) in eligible_pairs]

        if not eligible_pairs:
            # If there are no eligible pairs, the caller should decide what to do
            return None, None

        pair = np.random.randint(0, len(eligible_pairs))
        idx1, idx2 = eligible_pairs[pair]

        return population[idx1], population[idx2]

    def _mutate_random_individual(self, population: List[Any]) -> Any:
        max_attempts = 10
        for _ in range(max_attempts):
            idx = np.random.randint(0, len(population))
            individual = population[idx]
            for i, param in enumerate(self.optimizer_params):
                if random.random() < 0.5:
                    individual[i] = self.optimizer_params[param](individual[i])
            del individual.fitness.values
            new_config = self._individual_to_config(individual)
            if self._config_to_tuple(new_config) not in self.evaluated_configs:
                return individual
        return individual

    def _varOr(
        self,
        population: List[Any],
        toolbox: base.Toolbox,
        lambda_: int,
        cxpb: float,
        mutpb: float,
    ) -> List[Any]:
        offspring = []

        for _ in range(lambda_):
            op_choice = np.random.random()
            if op_choice < cxpb:  # Apply crossover
                ind1, ind2 = self._pick_two_individuals_eligible_for_crossover(population)
                if ind1 is not None:
                    child1, _ = toolbox.mate(ind1, ind2)
                    del child1.fitness.values

                    new_config = self._individual_to_config(child1)
                    config_tuple = self._config_to_tuple(new_config)
                    if config_tuple not in self.evaluated_configs:
                        offspring.append(child1)
                        self.evaluated_configs[config_tuple] = None
                    else:
                        # Handle duplicate by mutation or other means
                        child1 = self._mutate_random_individual(population)
                        offspring.append(child1)
                else:
                    # If no pair eligible for crossover, mutate instead
                    ind_mu = self._mutate_random_individual(population)
                    offspring.append(ind_mu)
            elif op_choice < cxpb + mutpb:  # Apply mutation
                ind = self._mutate_random_individual(population)
                offspring.append(ind)
            else:  # Apply reproduction
                idx = np.random.randint(0, len(population))
                offspring.append(toolbox.clone(population[idx]))

        return offspring

    @staticmethod
    def get_concurrency(max_concurrency: int, value: Optional[int] = None) -> int:
        """Retrieve the concurrency value.

        This method returns a mutated concurrency value if an initial value is provided.
        If no initial value is provided, it returns a random concurrency value between 1 and max_concurrency.

        Args:
            value (Optional[int]): The initial value for mutation. Defaults to None.

        Returns:
            int: The mutated or random concurrency value.
        """
        if value is not None:
            mutation = random.randint(-1, 1)
            mutated_value = min(max_concurrency, max(1, value + mutation))
            return mutated_value
        return random.randint(1, max_concurrency)

    def prepare_predictor_data(self, ind_config: Dict[str, Any]) -> Dict[str, Any]:
        """Prepare the data for the predictor.

        Args:
            ind_config (Dict[str, Any]): The individual configuration.

        Returns:
            Dict[str, Any]: The data for the predictor.
        """
        device_config = self.device_config.copy()
        # device_config.pop("cluster_id", None)
        # device_config.pop("node_id", None)
        # device_config.pop("node_name", None)
        # device_config.pop("id", None)
        # device_config.pop("type", None)
        model_analysis = ModelAnalysis(
            model=self.model,
            device_config=device_config,
            input_tokens=self.input_tokens,
            output_tokens=self.output_tokens,
            concurrency=ind_config["concurrency"],
            tp_size=ind_config["tensor_parallel_size"],
        )
        model_data = model_analysis.analyze()

        data = {
            "block_size": ind_config["block_size"],
            "concurrent_requests": ind_config["concurrency"],
            "decode_activation_memory_per_gpu": model_data["decode_activation_memory_per_gpu"],
            "decode_latency": model_data["decode_latency"],
            "decode_latency_fwd_attn": model_data["decode_latency_fwd_attn"],
            "decode_latency_fwd_input_embedding": model_data["decode_latency_fwd_input_embedding"],
            "decode_latency_fwd_layernorm": model_data["decode_latency_fwd_layernorm"],
            "decode_latency_fwd_mlp": model_data["decode_latency_fwd_mlp"],
            "decode_latency_fwd_output_embedding_loss": model_data["decode_latency_fwd_output_embedding_loss"],
            "decode_latency_fwd_tp_comm": model_data["decode_latency_fwd_tp_comm"],
            "decode_max_batch_size_per_gpu": model_data["decode_max_batch_size_per_gpu"],
            "decode_num_flops_fwd_total": model_data["decode_num_flops_fwd_total"],
            "decode_tokens_per_sec": model_data["decode_tokens_per_sec"],
            "kv_cache_latency": model_data["kv_cache_latency"],
            "kv_cache_memory_per_gpu": model_data["kv_cache_memory_per_gpu"],
            "max_num_seqs": ind_config["max_num_seqs"],
            "mean_input_tokens": self.input_tokens,
            "mean_output_tokens": self.output_tokens,
            "num_active_params_total": model_data["num_active_params_total"],
            "num_params_total": model_data["num_params_total"],
            "num_params_total_embedding": model_data["num_params_total_embedding"],
            "num_params_total_mlp": model_data["num_params_total_mlp"],
            "num_params_total_others": model_data["num_params_total_others"],
            "prefill_activation_memory_per_gpu": model_data["prefill_activation_memory_per_gpu"],
            "prefill_latency": model_data["prefill_latency"],
            "prefill_latency_fwd_attn": model_data["prefill_latency_fwd_attn"],
            "prefill_latency_fwd_input_embedding": model_data["prefill_latency_fwd_input_embedding"],
            "prefill_latency_fwd_layernorm": model_data["prefill_latency_fwd_layernorm"],
            "prefill_latency_fwd_mlp": model_data["prefill_latency_fwd_mlp"],
            "prefill_latency_fwd_output_embedding_loss": model_data["prefill_latency_fwd_output_embedding_loss"],
            "prefill_latency_fwd_tp_comm": model_data["prefill_latency_fwd_tp_comm"],
            "prefill_max_batch_size_per_gpu": model_data["prefill_max_batch_size_per_gpu"],
            "prefill_num_flops_fwd_total": model_data["prefill_num_flops_fwd_total"],
            "prefill_tokens_per_sec": model_data["prefill_tokens_per_sec"],
            "scheduler_delay_factor": ind_config["scheduler_delay_factor"],
            "tensor_parallel_size": ind_config["tensor_parallel_size"],
            "total_decode_latency": model_data["total_decode_latency"],
            "total_latency": model_data["total_latency"],
            "total_per_token_latency": model_data["total_per_token_latency"],
            "total_tokens_per_sec": model_data["total_tokens_per_sec"],
            "weight_memory_embedding_per_gpu": model_data["weight_memory_embedding_per_gpu"],
            "weight_memory_per_gpu": model_data["weight_memory_per_gpu"],
        }
        # print(f"Data: {data}")
        return data

    def apply_quantization_performance(self, ttft: float, throughput_per_user: float, e2e_latency: float) -> Tuple[float, float, float]:
        
        scale = 1.0
        if self.dtype == "bf16":
            scale = 1.0
        elif self.dtype == "INT8":
            scale = 1.3
        elif self.dtype == "INT4":
            scale = 1.5

        return ttft/scale, throughput_per_user * scale, e2e_latency / scale

    def _evaluate_func(self, population: List[Any]) -> List[Any]:
        # Evaluate the individuals with an invalid fitness
        individuals = [ind for ind in population if not ind.fitness.valid]

        for ind in individuals:
            ind_config = self._individual_to_config(ind)
            config_tuple = self._config_to_tuple(ind_config)

            try:
                ind_config["target_device"] = self.device_config["type"]
                if not check_config_compatibility(self.engine_name, ind_config):
                    ind.fitness.values = (0, 0, 0)
                    eval_result = EvaluationResult(ind_config, 0, 0, 0, 0, 0, (0, 0, 0), 0, 0)
                    self.evaluated_configs[config_tuple] = eval_result
                    continue
            except Exception as e:
                logger.error(f"Error evaluating {ind_config}: {e}")
                ind.fitness.values = (0, 0, 0)
                eval_result = EvaluationResult(ind_config, 0, 0, 0, 0, 0, (0, 0, 0), 0, 0)
                self.evaluated_configs[config_tuple] = eval_result
                continue

            data = self.prepare_predictor_data(ind_config)
            ttft, throughput_per_user, e2e_latency = self.benchmark_predictor(data)
            ttft, throughput_per_user, e2e_latency = self.apply_quantization_performance(ttft, throughput_per_user, e2e_latency)
            cost_per_million_tokens = self.cost_calculator.get_cost_per_million_tokens(
                throughput_per_user, ind_config["concurrency"], self.device_config, ind_config["tensor_parallel_size"]
            )
            logger.debug(
                f"Evaluating {ind_config}, Result TTFT: {ttft}, Throughput: {throughput_per_user}, E2E Latency: {e2e_latency}"
            )
            # TODO: Update the fitness calculation
            # Calculate fitness
            ttft_fitness = ttft / self.target_ttft
            e2e_latency_fitness = e2e_latency / self.target_e2e_latency
            throughput_per_user_fitness = throughput_per_user / self.target_throughput_per_user
            concurrency_fitness = max(0, ind_config["concurrency"] / self.max_concurrency)
            # cost_per_million_tokens_per_hour_fitness = 1 / cost_per_million_tokens

            error_rate = np.mean(
                (
                    max(0, min(1, ttft_fitness - 1)),
                    max(0, min(1, e2e_latency_fitness - 1)),
                    max(0, min(1, 1 - throughput_per_user_fitness)),
                )
            )

            fitness = (error_rate, concurrency_fitness, cost_per_million_tokens)
            # ttft_error = max(0, min(ttft_fitness - 1, 1))
            # e2e_latency_error = max(0, min(e2e_latency_fitness - 1, 1))
            # throughput_per_user_error = max(0, min(1 - throughput_per_user_fitness, 1))
            error_rate = np.mean((ttft_fitness - 1, e2e_latency_fitness - 1, 1 - throughput_per_user_fitness))
            total_memory_required = (
                data["kv_cache_memory_per_gpu"] + data["weight_memory_per_gpu"] * data["tensor_parallel_size"] + 20e9
            )
            eval_result = EvaluationResult(
                ind_config,
                total_memory_required,
                ttft,
                e2e_latency,
                throughput_per_user,
                ind_config["concurrency"],
                fitness,
                error_rate,
                cost_per_million_tokens,
            )
            self.evaluated_configs[config_tuple] = eval_result
            ind.fitness.values = fitness

        return individuals

    def _is_within_margin(self, eval_result: EvaluationResult) -> bool:
        ttft_upper = self.target_ttft * (1 + self.error_threshold)
        e2e_latency_upper = self.target_e2e_latency * (1 + self.error_threshold)
        throughput_per_user_lower = self.target_throughput_per_user * (1 - self.error_threshold)

        return (
            eval_result.ttft <= ttft_upper
            and eval_result.e2e_latency <= e2e_latency_upper
            and eval_result.throughput_per_user >= throughput_per_user_lower
        )

    def _check_convergence(self, population: List[Any]) -> bool:
        # Check for convergence
        # best_individual = tools.selBest(population, k=1)[0]
        # best_config = self._individual_to_config(best_individual)
        # eval_result = self.evaluated_configs[self._config_to_tuple(best_config)]
        # if eval_result is not None:
        #     logger.info(f"Best fitness: {eval_result.fitness}")
        # else:
        #     logger.warning("Best evaluation result is None.")

        top_5_individuals = tools.selBest(population, k=5)
        top_5_configs: List[EvaluationResult] = [
            config
            for config in (
                self.evaluated_configs.get(self._config_to_tuple(self._individual_to_config(ind)))
                for ind in top_5_individuals
            )
            if config is not None
        ]
        if len(top_5_configs) == 0:
            logger.warning("No top 5 evaluation results found.")
            return False

        if all(config is not None for config in top_5_configs):
            logger.info(f"Top 5 fitness: {[config.fitness for config in top_5_configs]}")
        else:
            logger.warning("One or more of the top 5 evaluation results are None.")
            return False

        config_added = False

        for top_config in top_5_configs:
            if (len(self.top_configs) < self.top_k or top_config.fitness > self.top_configs[-1].fitness) and not any(
                config.fitness == top_config.fitness for config in self.top_configs
            ):
                self.top_configs.append(top_config)
                self.top_configs = deque(
                    sorted(self.top_configs, key=lambda x: x.fitness, reverse=False),
                    maxlen=self.top_k,
                )
                config_added = True
                self.generations_since_improvement = 0

            if self._is_within_margin(top_config) and not config_added:
                self.generations_since_improvement += 1

        # Check if we have top_k configs and haven't improved for convergence_generations
        return (
            len(self.top_configs) == self.top_k and self.generations_since_improvement >= self.convergence_generations
        )

    def evolve(self) -> List[EvaluationResult]:
        """Evolve the population over a number of generations.

        This method creates an initial population and evolves it over a specified
        number of generations. During each generation, it applies genetic operators
        such as crossover, mutation, and reproduction to create offspring. The
        population is then evaluated and the best individuals are selected for the
        next generation. Finally, the best individual from the final population is
        returned.

        Returns:
            Dict[str, Any]: The configuration of the best individual from the final population.
        """
        # Create initial population
        population = self.toolbox.population(n=self.population_size)

        # Evaluate the initial population
        population = self.toolbox.evaluate(population)

        # Number of elite individuals to preserve
        num_elite = int(self.population_size * self.elite_ratio)

        # Evolve the population
        for gen in tqdm(range(self.generation), desc="Running evolution"):
            # Select and preserve elite individuals
            elite = tools.selBest(population, k=num_elite)
            # Remove duplicates from elite
            elite = list({self._config_to_tuple(self._individual_to_config(ind)): ind for ind in elite}.values())
            num_elite = len(elite)
            # Select the worst individuals to be replaced
            not_elite = tools.selWorst(population, k=self.population_size - num_elite)
            offspring = self._varOr(
                population,
                self.toolbox,
                lambda_=self.population_size,
                cxpb=0.5,
                mutpb=0.2,
            )

            # Ensure uniqueness in offspring
            unique_offspring = []
            for ind in offspring:
                config = self._individual_to_config(ind)
                config_tuple = self._config_to_tuple(config)
                if config_tuple not in self.evaluated_configs:
                    unique_offspring.append(ind)
                    self.evaluated_configs[config_tuple] = None

            # If we don't have enough unique offspring, generate more
            while len(unique_offspring) < self.population_size - num_elite:
                new_ind = self.toolbox.individual()
                config = self._individual_to_config(new_ind)
                config_tuple = self._config_to_tuple(config)
                if config_tuple not in self.evaluated_configs:
                    unique_offspring.append(new_ind)
                    self.evaluated_configs[config_tuple] = None

            offspring = self.toolbox.evaluate(unique_offspring)

            # Combine elite, population, and offspring
            combined_pop = not_elite + offspring

            # Ensure all individuals have valid fitness values
            valid_individuals = [ind for ind in combined_pop if ind.fitness.valid]

            # If there are no valid individuals, re-evaluate the entire population
            if not valid_individuals:
                logger.warning("No valid individuals found. Re-evaluating entire population.")
                valid_individuals = self.toolbox.evaluate(combined_pop)

            # Select the next generation population
            population[:] = elite + self.toolbox.select(valid_individuals, self.population_size - num_elite)

            if self._check_convergence(population):
                logger.debug(f"Convergence reached at generation {gen}")
                break

            # Early stop if no new unique combinations are found
            if len(unique_offspring) == 0:
                logger.info(f"Early stopping at generation {gen} due to no new unique combinations.")
                break

        # top_5_individuals = tools.selBest(population, k=5)
        top_5_scores = list(self.top_configs)  # Convert deque to list
        # top_5_scores = [
        #     self.evaluated_configs[self._config_to_tuple(self._individual_to_config(ind))] for ind in top_5_individuals
        # ]
        logger.info(f"Top 5 scores: {top_5_scores}")

        # kvcache, config, predictions, score/error rate
        return top_5_scores
