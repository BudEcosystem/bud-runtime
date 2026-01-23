# budsim Service Documentation

---

## Overview

budsim is the performance simulation and optimization service that uses machine learning (XGBoost) and genetic algorithms (DEAP) to predict and optimize model deployment configurations.

---

## Service Identity

| Property | Value |
|----------|-------|
| **App ID** | budsim |
| **Port** | 9083 |
| **Database** | budsim_db (PostgreSQL) |
| **Language** | Python 3.11 |
| **Framework** | FastAPI |

---

## Responsibilities

- Predict inference performance (TTFT, throughput, latency)
- Optimize deployment configuration (TP, PP, batch size, replicas)
- Maintain hardware profile database
- Run multi-objective genetic algorithm optimization
- Store and retrieve simulation results

---

## Optimization Methods

### REGRESSOR Method

ML-based optimization using XGBoost + DEAP genetic algorithm:

- **Input**: Model architecture, hardware specs, performance targets
- **Optimizes**: All engine parameters (TP, PP, batch size, max_num_seqs, etc.)
- **Output**: Predicted performance metrics with optimal configuration

### HEURISTIC Method

Memory-based calculations for faster results:

- **Input**: Model architecture, GPU memory
- **Optimizes**: Only TP/PP parameters
- **Output**: Configuration based on memory constraints

### Method Selection

```python
def _is_heuristic_config(config: SimulationConfig) -> bool:
    return config.simulation_method == SimulationMethod.HEURISTIC
```

---

## API Endpoints

| Method | Path | Description |
|--------|------|-------------|
| POST | `/simulate` | Run performance simulation |
| POST | `/optimize` | Run optimization for deployment |
| GET | `/simulations` | List simulation results |
| GET | `/simulations/{id}` | Get simulation details |
| GET | `/hardware-profiles` | List hardware profiles |
| POST | `/hardware-profiles` | Add hardware profile |

---

## Data Models

### Simulation

```python
class Simulation(Base):
    id: UUID
    model_id: UUID
    hardware_profile_id: UUID
    method: SimulationMethod  # REGRESSOR, HEURISTIC
    input_config: dict
    result: dict  # Predicted metrics
    optimal_config: dict  # Recommended configuration
    created_at: datetime
```

### HardwareProfile

```python
class HardwareProfile(Base):
    id: UUID
    name: str
    gpu_type: str  # A100, H100, L40S, etc.
    gpu_memory_gb: int
    gpu_count: int
    interconnect: str  # NVLink, PCIe
    specs: dict  # Additional specifications
```

---

## Configuration

| Variable | Description | Default |
|----------|-------------|---------|
| `DATABASE_URL` | PostgreSQL connection string | Required |
| `MODEL_PATH` | Path to XGBoost model | `./models/xgboost.json` |
| `OPTIMIZATION_TIMEOUT` | Max optimization time (seconds) | `300` |
| `POPULATION_SIZE` | Genetic algorithm population | `50` |
| `GENERATIONS` | Genetic algorithm generations | `100` |

---

## Development

```bash
cd services/budsim
./deploy/start_dev.sh --build

# Run tests
pytest
```

---

## Related Documents

- [BudSim User Guide](../ai-ml/budsim-user-guide.md)
- [Resource Optimization Guide](../ai-ml/resource-optimization.md)
