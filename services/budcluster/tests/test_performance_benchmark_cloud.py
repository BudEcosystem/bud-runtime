from budcluster.deployment.performance import DeploymentPerformance

def test_performance_benchmark_cloud():
    performance_benchmark = DeploymentPerformance(
        deployment_url="http://20.244.107.114:13025/bud-test-39417b7d/v1",
        model="test",
        concurrency=1,
        input_tokens=50,
        output_tokens=100,
        provider_type="cloud"
    )
    benchmark_result = performance_benchmark.run_performance_test()
    print(benchmark_result)
    
def test_performance_benchmark_local():
    performance_benchmark = DeploymentPerformance(
        deployment_url="http://20.244.107.114:10701/bud-test-b966a4f6/v1",
        model="/data/models-registry/meta-llama_llama-3_2_03e2deb8/vllm_quant_model",
        concurrency=1,
        input_tokens=50,
        output_tokens=100,
        provider_type="local"
    )
    benchmark_result = performance_benchmark.run_performance_test()
    print(benchmark_result)

# test_performance_benchmark_cloud()
test_performance_benchmark_local()
