import { notification, Space } from "antd";
import { PrimaryButton, SecondaryButton } from "../ui/bud/form/Buttons";
import { Text_12_400_757575, Text_14_400_EEEEEE } from "../ui/text";

interface openWarningProps {
  title?: string;
  description?: string;
  deleteDisabled?: boolean;
  onDelete?: () => void;
  onCancel?: () => void;
}

export const openWarning = ({
  title,
  description,
  onDelete,
  onCancel,
  deleteDisabled = false
}: openWarningProps) => {
  const key = `${title}-delete-notification`;

  const updateNotificationMessage = (newDescription: string) => {
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
            <Text_14_400_EEEEEE>
              {title}
            </Text_14_400_EEEEEE>
            <Text_12_400_757575>{newDescription}</Text_12_400_757575>
          </div>
        </div>
      ),
      placement: "bottomRight",
      duration: 0,
      closeIcon: null,
      style: {
        width: "30.9375rem",
        background: "#101010",
        borderRadius: 6,
        border: "1px solid #1F1F1F",
        backdropFilter: "blur(10px)",
      },
      btn: (
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

  updateNotificationMessage(description || '');
  return updateNotificationMessage;
};