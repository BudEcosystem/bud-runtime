import asyncio
import json
from datetime import datetime, timedelta
from budapp.shared.promql_service import PrometheusMetricsClient

async def test_node_metrics_and_events():
    """Test getting node metrics and events"""
    try:
        promql_service = PromQLService(cluster_name="dff4578f-039e-4be4-aa36-db7932e404fa")
        metrics = await promql_service.get_nodes_metrics_and_events()

        print("\n=== Node Metrics and Events ===")

        # Validate response structure
        assert 'nodes' in metrics, "Response should contain 'nodes' key"
        assert isinstance(metrics['nodes'], list), "'nodes' should be a list"

        for node in metrics['nodes']:
            # Validate basic node structure
            assert 'name' in node, "Each node should have a name"
            assert 'metrics' in node, "Each node should have metrics"

            # Validate metrics structure
            metrics_data = node['metrics']
            assert all(key in metrics_data for key in [
                'nodeReadyStatus', 'podsAvailable', 'cpuRequests',
                'memoryRequests', 'networkIO', 'events'
            ]), "Missing required metrics"

            # Validate nodeReadyStatus format
            ready_status = metrics_data['nodeReadyStatus']
            assert 'status' in ready_status, "Ready status should have status field"
            assert 'percentage' in ready_status, "Ready status should have percentage field"
            assert ready_status['status'] in ['Ready', 'NotReady'], "Invalid ready status"
            assert isinstance(ready_status['percentage'], int), "Ready status percentage should be integer"
            assert 0 <= ready_status['percentage'] <= 100, "Ready status percentage should be 0-100"

            # Validate pods format
            pods = metrics_data['podsAvailable']
            assert all(key in pods for key in ['current', 'desired', 'percentage']), "Invalid pods format"
            assert isinstance(pods['current'], int), "Pods current should be integer"
            assert isinstance(pods['desired'], int), "Pods desired should be integer"
            assert isinstance(pods['percentage'], int), "Pods percentage should be integer"
            assert 0 <= pods['percentage'] <= 100, "Pods percentage should be 0-100"

            # Validate memory format
            memory = metrics_data['memoryRequests']
            assert 'unit' in memory and memory['unit'] == 'GiB', "Memory should be in GiB"
            assert isinstance(memory['current'], int), "Memory current should be integer"
            assert isinstance(memory['allocatable'], int), "Memory allocatable should be integer"
            assert isinstance(memory['percentage'], int), "Memory percentage should be integer"
            assert 0 <= memory['percentage'] <= 100, "Memory percentage should be 0-100"

            # Validate CPU format
            cpu = metrics_data['cpuRequests']
            assert all(key in cpu for key in ['current', 'allocatable', 'percentage']), "Invalid CPU format"
            assert isinstance(cpu['current'], float), "CPU current should be float"
            assert isinstance(cpu['percentage'], float), "CPU percentage should be float"
            assert 0 <= cpu['percentage'] <= 100, "CPU percentage should be 0-100"

            # Validate network format
            network = metrics_data['networkIO']
            assert 'unit' in network and network['unit'] == 'KiB/s', "Network should be in KiB/s"
            assert 'trend' in network, "Network should have trend"
            assert network['trend'] in ['stable', 'fluctuating'], "Invalid network trend"
            assert isinstance(network['current'], float), "Network current should be float"
            assert 'receive' in network and isinstance(network['receive'], float), "Network receive should be float"
            assert 'transmit' in network and isinstance(network['transmit'], float), "Network transmit should be float"

            # Validate network history if present
            if 'history' in network:
                assert isinstance(network['history'], list), "Network history should be a list"
                for data_point in network['history']:
                    assert 'timestamp' in data_point, "History data point should have timestamp"
                    assert 'value' in data_point, "History data point should have value"
                    assert isinstance(data_point['value'], float), "History value should be float"

            # Validate events format
            events = metrics_data['events']
            assert 'count' in events, "Events should have count"
            assert 'status' in events, "Events should have status"
            assert events['status'] in ['normal', 'warning'], "Invalid event status"

        # Write formatted metrics to file for inspection
        with open("node_metrics.json", "w") as f:
            json.dump(metrics, f, indent=2)
        print("Node metrics written to node_metrics.json")

        # Print validation summary
        print(f"\nValidation Summary:")
        print(f"Number of nodes: {len(metrics['nodes'])}")
        for node in metrics['nodes']:
            print(f"\nNode: {node['name']}")
            print(f"Ready Status: {node['metrics']['nodeReadyStatus']['status']}")
            print(f"Pods: {node['metrics']['podsAvailable']['current']}/{node['metrics']['podsAvailable']['desired']}")
            print(f"CPU Usage: {node['metrics']['cpuRequests']['percentage']}%")
            print(f"Memory Usage: {node['metrics']['memoryRequests']['percentage']}%")
            print(f"Network I/O: {node['metrics']['networkIO']['current']} {node['metrics']['networkIO']['unit']}")
            print(f"Events: {node['metrics']['events']['count']} ({node['metrics']['events']['status']})")

    except AssertionError as e:
        print(f"Validation Error: {str(e)}")
        raise
    except Exception as e:
        print(f"Error in test_node_metrics_and_events: {str(e)}")
        raise

async def run_all_tests():
    """Run all test functions"""
    print("\nStarting tests...")
    start_time = datetime.now()

    try:
        await test_node_metrics_and_events()
        print("\nAll tests completed successfully!")
    except Exception as e:
        print(f"\nTests failed with error: {str(e)}")
    finally:
        end_time = datetime.now()
        duration = (end_time - start_time).total_seconds()
        print(f"\nTotal test duration: {duration:.2f} seconds")

def main():
    """Main function"""
    print("=== Starting PromQLService Tests ===")
    print(f"Time: {datetime.now().isoformat()}")
    print("Cluster: dff4578f-039e-4be4-aa36-db7932e404fa")
    print("================================")

    asyncio.run(run_all_tests())

    print("\n=== Tests Complete ===")

if __name__ == "__main__":
    main()
