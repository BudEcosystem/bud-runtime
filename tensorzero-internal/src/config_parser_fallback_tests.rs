#[cfg(test)]
mod tests {
    use crate::config_parser::Config;
    use std::collections::{HashMap, HashSet};

    #[test]
    fn test_detect_circular_fallbacks_no_cycle() {
        let mut fallback_graph = HashMap::new();
        fallback_graph.insert("model-a".to_string(), vec!["model-b".to_string()]);
        fallback_graph.insert("model-b".to_string(), vec!["model-c".to_string()]);

        let config = Config::default();
        let mut visited = HashSet::new();
        let mut path = Vec::new();
        let result =
            config.check_fallback_cycle("model-a", &fallback_graph, &mut visited, &mut path);
        assert!(result.is_ok());
    }

    #[test]
    fn test_detect_circular_fallbacks_direct_cycle() {
        let mut fallback_graph = HashMap::new();
        fallback_graph.insert("model-a".to_string(), vec!["model-a".to_string()]);

        let config = Config::default();
        let mut visited = HashSet::new();
        let mut path = Vec::new();
        let result =
            config.check_fallback_cycle("model-a", &fallback_graph, &mut visited, &mut path);
        assert!(result.is_err());

        let chain = result.unwrap_err();
        assert!(chain.contains(&"model-a".to_string()));
    }

    #[test]
    fn test_detect_circular_fallbacks_indirect_cycle() {
        let mut fallback_graph = HashMap::new();
        fallback_graph.insert("model-a".to_string(), vec!["model-b".to_string()]);
        fallback_graph.insert("model-b".to_string(), vec!["model-c".to_string()]);
        fallback_graph.insert("model-c".to_string(), vec!["model-a".to_string()]);

        let config = Config::default();
        let mut visited = HashSet::new();
        let mut path = Vec::new();
        let result =
            config.check_fallback_cycle("model-a", &fallback_graph, &mut visited, &mut path);
        assert!(result.is_err());

        let chain = result.unwrap_err();
        // The cycle should contain all three models
        assert!(chain.contains(&"model-a".to_string()));
        assert!(chain.contains(&"model-b".to_string()));
        assert!(chain.contains(&"model-c".to_string()));
    }

    #[test]
    fn test_detect_circular_fallbacks_multiple_fallbacks() {
        let mut fallback_graph = HashMap::new();
        // model-a has two fallbacks, but no cycles
        fallback_graph.insert(
            "model-a".to_string(),
            vec!["model-b".to_string(), "model-c".to_string()],
        );
        fallback_graph.insert("model-b".to_string(), vec!["model-d".to_string()]);

        let config = Config::default();
        let mut visited = HashSet::new();
        let mut path = Vec::new();
        let result =
            config.check_fallback_cycle("model-a", &fallback_graph, &mut visited, &mut path);
        assert!(result.is_ok());
    }

    #[test]
    fn test_detect_circular_fallbacks_complex_cycle() {
        let mut fallback_graph = HashMap::new();
        // Create a more complex graph with a cycle
        fallback_graph.insert("model-a".to_string(), vec!["model-b".to_string()]);
        fallback_graph.insert(
            "model-b".to_string(),
            vec!["model-c".to_string(), "model-d".to_string()],
        );
        fallback_graph.insert("model-c".to_string(), vec!["model-e".to_string()]);
        fallback_graph.insert("model-d".to_string(), vec!["model-f".to_string()]);
        fallback_graph.insert("model-f".to_string(), vec!["model-b".to_string()]); // Creates cycle: b -> d -> f -> b

        let config = Config::default();
        let mut visited = HashSet::new();
        let mut path = Vec::new();
        let result =
            config.check_fallback_cycle("model-a", &fallback_graph, &mut visited, &mut path);
        assert!(result.is_err());

        let chain = result.unwrap_err();
        // The cycle should be detected
        assert!(chain.len() > 0);
    }
}
