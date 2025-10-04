import React, { useCallback, useEffect, useState } from 'react';
import { Dialog, Button, Text, Flex, Box, VisuallyHidden } from '@radix-ui/themes';
import { Cross1Icon } from '@radix-ui/react-icons';
import { TextInput, SelectInput } from '@/components/ui/input';
import { Text_12_300_44474D, Text_12_400_787B83, Text_16_600_FFFFFF } from '@/components/ui/text';
import { ButtonInput } from '@/components/ui/button';
import { useCluster } from '@/hooks/useCluster';
import { errorToast } from '@/components/toast';

const ACCESS_MODE_OPTIONS = [
  { label: 'ReadWriteOnce', value: 'ReadWriteOnce', description: 'Single node read/write access.' },
  { label: 'ReadWriteMany', value: 'ReadWriteMany', description: 'Multiple nodes read/write (shared storage).' },
  { label: 'ReadOnlyMany', value: 'ReadOnlyMany', description: 'Multiple nodes read-only access.' },
  { label: 'ReadWriteOncePod', value: 'ReadWriteOncePod', description: 'Single pod read/write access.' },
];

interface ClusterSettingsPopupProps {
  isOpen: boolean;
  onOpenChange: (isOpen: boolean) => void;
  clusterId: string;
  clusterName: string;
}

interface FormData {
  default_storage_class?: string;
  default_access_mode?: string;
}

interface FormErrors {
  default_storage_class?: string;
}

const ClusterSettingsPopup: React.FC<ClusterSettingsPopupProps> = ({
  isOpen,
  onOpenChange,
  clusterId,
  clusterName,
}) => {
  const {
    getClusterSettings,
    createClusterSettings,
    updateClusterSettings,
    deleteClusterSettings
  } = useCluster();

  const [formData, setFormData] = useState<FormData>({});
  const [errors, setErrors] = useState<FormErrors>({});
  const [isLoading, setIsLoading] = useState(false);
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [hasExistingSettings, setHasExistingSettings] = useState(false);

  // Load existing settings when popup opens
  useEffect(() => {
    if (isOpen && clusterId) {
      loadClusterSettings();
    }
  }, [isOpen, clusterId]);

  const loadClusterSettings = async () => {
    setIsLoading(true);
    try {
      const settings = await getClusterSettings(clusterId);
      if (settings) {
        setFormData({
          default_storage_class: settings.default_storage_class || '',
          default_access_mode: settings.default_access_mode || '',
        });
        setHasExistingSettings(true);
      } else {
        setFormData({
          default_storage_class: '',
          default_access_mode: '',
        });
        setHasExistingSettings(false);
      }
    } catch (error) {
      console.error('Error loading cluster settings:', error);
      errorToast('Failed to load cluster settings');
    } finally {
      setIsLoading(false);
    }
  };

  const handleChange = (name: string, value: string) => {
    const newErrors = { ...errors };

    // Validate storage class name
    if (name === 'default_storage_class' && value) {
      if (!/^[a-zA-Z0-9.-]*$/.test(value)) {
        newErrors.default_storage_class = 'Storage class name can only contain letters, numbers, dots, and hyphens';
      } else if (value.startsWith('-') || value.endsWith('-')) {
        newErrors.default_storage_class = 'Storage class name cannot start or end with a hyphen';
      } else {
        delete newErrors.default_storage_class;
      }
    } else {
      delete newErrors[name];
    }

    setErrors(newErrors);
    setFormData(prev => ({ ...prev, [name]: value }));
  };

  const validateForm = (): boolean => {
    const newErrors: FormErrors = {};

    // Storage class is optional but must be valid if provided
    if (formData.default_storage_class) {
      const storageClass = formData.default_storage_class.trim();
      if (!/^[a-zA-Z0-9.-]*$/.test(storageClass)) {
        newErrors.default_storage_class = 'Storage class name can only contain letters, numbers, dots, and hyphens';
      } else if (storageClass.startsWith('-') || storageClass.endsWith('-')) {
        newErrors.default_storage_class = 'Storage class name cannot start or end with a hyphen';
      }
    }

    setErrors(newErrors);
    return Object.keys(newErrors).length === 0;
  };

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();

    if (!validateForm()) {
      return;
    }

    setIsSubmitting(true);
    try {
      const data = {
        default_storage_class: formData.default_storage_class?.trim() || null,
        default_access_mode: formData.default_access_mode || null,
      };

      if (hasExistingSettings) {
        await updateClusterSettings(clusterId, data);
      } else {
        await createClusterSettings(clusterId, data);
      }

      onOpenChange(false);
    } catch (error) {
      console.error('Error saving cluster settings:', error);
      errorToast('Failed to save cluster settings');
    } finally {
      setIsSubmitting(false);
    }
  };

  const handleDelete = async () => {
    if (!hasExistingSettings) return;

    if (window.confirm('Are you sure you want to delete these cluster settings? This will reset all settings to defaults.')) {
      setIsSubmitting(true);
      try {
        await deleteClusterSettings(clusterId);
        setFormData({ default_storage_class: '', default_access_mode: '' });
        setHasExistingSettings(false);
      } catch (error) {
        console.error('Error deleting cluster settings:', error);
        errorToast('Failed to delete cluster settings');
      } finally {
        setIsSubmitting(false);
      }
    }
  };

  const handleClose = () => {
    setFormData({});
    setErrors({});
    setHasExistingSettings(false);
    onOpenChange(false);
  };

  return (
    <Dialog.Root open={isOpen} onOpenChange={handleClose}>
      <Dialog.Content style={{ maxWidth: 500, padding: 0 }}>
        <VisuallyHidden>
          <Dialog.Title>Cluster Settings</Dialog.Title>
          <Dialog.Description>Configure default settings for {clusterName}</Dialog.Description>
        </VisuallyHidden>

        <Box style={{ padding: '24px 32px' }}>
          <Flex justify="between" align="center" mb="4">
            <Box>
              <Text size="5" weight="bold" color="gray">
                Cluster Settings
              </Text>
              <Text_12_300_44474D style={{ marginTop: '4px' }}>
                Configure default settings for {clusterName}
              </Text_12_300_44474D>
            </Box>
            <Dialog.Close>
              <Button variant="ghost" size="2">
                <Cross1Icon />
              </Button>
            </Dialog.Close>
          </Flex>

          {isLoading ? (
            <Flex justify="center" align="center" py="8">
              <Text>Loading cluster settings...</Text>
            </Flex>
          ) : (
            <form onSubmit={handleSubmit}>
              <Box mb="4">
                <TextInput
                  label="Default Storage Class"
                  placeholder="e.g., gp2, nfs-storage-class, fast-ssd (leave empty for system default)"
                  value={formData.default_storage_class || ''}
                  onChange={(value) => handleChange('default_storage_class', value)}
                  error={errors.default_storage_class}
                  helperText="Optional: Specify the default storage class for deployments on this cluster. If not specified, the system default will be used."
                />
              </Box>

              <Box mb="4">
                <Text size="2" weight="bold" color="gray">
                  Preferred Access Mode
                </Text>
                <Text_12_300_44474D style={{ marginTop: '4px', marginBottom: '12px' }}>
                  Optional: Choose how persistent volumes should be mounted. Pick the mode recommended for your storage class.
                </Text_12_300_44474D>
                <SelectInput
                  placeholder="Select access mode"
                  value={formData.default_access_mode || ''}
                  selectItems={ACCESS_MODE_OPTIONS}
                  onValueChange={(value) => handleChange('default_access_mode', value)}
                />
              </Box>

              <Flex gap="3" mt="6" justify="end">
                {hasExistingSettings && (
                  <Button
                    type="button"
                    variant="soft"
                    color="red"
                    onClick={handleDelete}
                    disabled={isSubmitting}
                  >
                    Delete Settings
                  </Button>
                )}
                <Button
                  type="button"
                  variant="soft"
                  color="gray"
                  onClick={handleClose}
                  disabled={isSubmitting}
                >
                  Cancel
                </Button>
                <Button
                  type="submit"
                  disabled={isSubmitting}
                  style={{
                    backgroundColor: '#007AFF',
                    color: 'white',
                  }}
                >
                  {isSubmitting ? 'Saving...' : hasExistingSettings ? 'Update Settings' : 'Create Settings'}
                </Button>
              </Flex>
            </form>
          )}
        </Box>
      </Dialog.Content>
    </Dialog.Root>
  );
};

export default ClusterSettingsPopup;
