import sys
import os
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from budapp.shared.promql_service import PrometheusMetricsClient

def main():
    prometheus_client = PrometheusMetricsClient(
        base_url="https://metric.bud.studio",
        cluster_id="8b84bf44-b16e-425c-860a-78a103bf4ec6"
    )
    node_metrics = prometheus_client.get_node_metrics()
    print(node_metrics)
    
    

if __name__ == "__main__":
    main()