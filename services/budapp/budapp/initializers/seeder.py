from budapp.initializers.base_keycloak_seeder import BaseKeycloakSeeder
from budapp.initializers.cloud_provider_seeder import CloudProviderSeeder
from budapp.initializers.dataset_seeder import DatasetSeeder

from budapp.initializers.provider_seeder import ProviderSeeder
from budapp.initializers.guardrails_seeder import GuardrailsSeeder
from budapp.initializers.icon_seeder import IconSeeder
from budapp.initializers.quantization_method_seeder import QuantizationMethodSeeder
from budapp.initializers.template_seeder import TemplateSeeder


seeders = {
    # "keycloak": BaseKeycloakSeeder,
    # "user": UserSeeder,
    # "provider": ProviderSeeder,  # Commented out for budconnect sync
    # "cloud_model": CloudModelSeeder,  # Commented out for budconnect sync
    # "icon": IconSeeder,
    # "template": TemplateSeeder,
    # "cloud_provider": CloudProviderSeeder,
    # "quantization_method": QuantizationMethodSeeder,
    # "datasets": DatasetSeeder,
    "guardrails": GuardrailsSeeder,
}
