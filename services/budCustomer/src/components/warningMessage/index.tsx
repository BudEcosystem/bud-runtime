import { Space } from "antd";
import type { NotificationInstance } from "antd/es/notification/interface";
import { PrimaryButton, SecondaryButton } from "../ui/bud/form/Buttons";
import { Text_12_400_757575, Text_14_400_EEEEEE } from "../ui/text";

interface openWarningProps {
  title?: string;
  description?: string;
  deleteDisabled?: boolean;
  onDelete?: () => void;
  onCancel?: () => void;
  notification: NotificationInstance;
}

export const openWarning = ({
  title,
  description,
  onDelete,
  onCancel,
  deleteDisabled = false,
  notification,
}: openWarningProps) => {
  const key = `${title}-delete-notification`;

  const updateNotificationMessage = (newDescription: string) => {
    // Check if light theme is active
    const isLightTheme = document.documentElement.getAttribute('data-theme') === 'light';

    notification.open({
      key,
      message: (
        <div style={{ display: "flex", alignItems: "flex-start" }}>
          <img
            src="/images/drawer/warning.png"
            alt="Warning"
            style={{
              width: "55px",
              marginRight: 24,
              marginLeft: 6,
              marginTop: 11,
            }}
          />
          <div className="flex flex-col gap-y-[12px] pt-[5px]">
            <div style={{
              color: isLightTheme ? '#1A1A1A' : '#EEEEEE',
              fontSize: '14px',
              fontWeight: 400
            }}>
              {title}
            </div>
            <div style={{
              color: isLightTheme ? '#666666' : '#757575',
              fontSize: '12px',
              fontWeight: 400
            }}>
              {newDescription}
            </div>
          </div>
        </div>
      ),
      placement: "bottomRight",
      duration: 0,
      closeIcon: null,
      style: {
        width: "30.9375rem",
        background: isLightTheme ? '#FFFFFF' : '#101010',
        borderRadius: 6,
        border: isLightTheme ? '1px solid #E0E0E0' : '1px solid #1F1F1F',
        backdropFilter: "blur(10px)",
      },
      actions: (
        <Space>
          <SecondaryButton
            text="Cancel"
            onClick={() => {
              notification.destroy(key);
              if (onCancel) onCancel();
            }}
          />
          {!deleteDisabled && (
            <PrimaryButton
              text="Delete"
              disabled={deleteDisabled}
              onClick={() => {
                deleteDisabled = true; // Disable the button within the closure
                if (onDelete) onDelete();
              }}
            />
          )}
        </Space>
      ),
    });
  };

  updateNotificationMessage(description || "");
  return updateNotificationMessage;
};
