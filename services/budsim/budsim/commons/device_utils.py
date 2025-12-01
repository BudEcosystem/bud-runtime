#  -----------------------------------------------------------------------------
#  Copyright (c) 2024 Bud Ecosystem Inc.
#  #
#  Licensed under the Apache License, Version 2.0 (the "License");
#  you may not use this file except in compliance with the License.
#  You may obtain a copy of the License at
#  #
#      http://www.apache.org/licenses/LICENSE-2.0
#  #
#  Unless required by applicable law or agreed to in writing, software
#  distributed under the License is distributed on an "AS IS" BASIS,
#  WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
#  See the License for the specific language governing permissions and
#  limitations under the License.
#  -----------------------------------------------------------------------------

"""Device type utility functions."""


def normalize_device_type(device_type: str) -> str:
    """Normalize device type to generic type for matching.

    Maps specific device type variants to their generic types:
    - cpu_high, cpu_low -> cpu
    - cuda -> cuda
    - rocm -> rocm

    Args:
        device_type: The device type string (e.g., 'cpu_high', 'CUDA', 'cpu')

    Returns:
        Normalized device type in lowercase (e.g., 'cpu', 'cuda', 'rocm')
    """
    device_type_lower = device_type.lower()

    # Map CPU variants to generic 'cpu'
    if device_type_lower.startswith("cpu"):
        return "cpu"

    # Map other device types to their base type
    # rocm variants, cuda variants, etc.
    return device_type_lower
