import React, { useContext } from "react";
import { Form, FormRule, message, Upload } from "antd";
import FloatLabel from "@/components/ui/bud/dataEntry/FloatLabel";
import InfoLabel from "@/components/ui/bud/dataEntry/InfoLabel";
import type { UploadFile, UploadProps } from "antd";
import { BudFormContext } from "@/components/ui/bud/context/BudFormContext";

export interface BudInputProps {
  onClick?: () => void;
  onFocus?: () => void;
  onBlur?: () => void;
  onChange?: (value: any) => void;
  name: string;
  label: string;
  value?: string;
  placeholder?: string;
  disabled?: boolean;
  ClassNames?: string;
  style?: React.CSSProperties;
  rules: FormRule[];
  text: React.ReactNode;
  hint: React.ReactNode;
  acceptedFileTypes: string[];
  maxCount?: number;
  required?: boolean;
  infoText?: string;
}

const FileInput: React.FC<BudInputProps> = (props) => {
  const { Dragger } = Upload;
  const { form } = useContext(BudFormContext);
  const [fileList, setFileList] = React.useState<UploadFile[]>([]);

  // Rename this to avoid conflict with `props`
  const uploadProps: UploadProps = {
    name: "file",
    multiple: props.maxCount > 1,
    onDrop(e) {},
    onChange(info) {
      const { status } = info.file;
      if (status === "done") {
        // message.success(`${info.file.name} file uploaded successfully.`);
      } else if (status === "error") {
        // message.error(`${info.file.name} file upload failed.`);
      }
    },
    beforeUpload(file, fileList) {
      if (file.size > 10000000) {
        message.error("File size must be less than 10MB");
        return false;
      }
      form.setFieldsValue({ [props.name]: file });
      setFileList([...fileList]);
      props.onChange && props.onChange(file);
      return true;
    },
  };

  return (
    <Form.Item
      name={props.name}
      rules={props.rules}
      validateTrigger={["onChange"]}
      hasFeedback
      className="mb-[.5rem]"
    >
      <div className={`floating-textarea`}>
        <FloatLabel
          label={
            <InfoLabel
              text={props.label}
              content={props.infoText || "Upload a file"}
              required={props.required}
            />
          }
        >
          <Dragger
            {...uploadProps}
            accept={props.acceptedFileTypes?.join(",")}
            maxCount={props.maxCount || 1}
            showUploadList={false}
          >
            {fileList.length === 0 ? (
              <div className="pt-[.3rem]">
                <p className="ant-upload-drag-icon w-full flex justify-center items-center mb-[.4rem]">
                  <svg
                    width="0.875rem"
                    height="0.875rem"
                    viewBox="0 0 14 15"
                    fill="none"
                    xmlns="http://www.w3.org/2000/svg"
                  >
                    <path
                      fillRule="evenodd"
                      clipRule="evenodd"
                      d="M3.26145 4.77552C3.00372 4.77552 2.79478 4.98445 2.79478 5.24219L2.79478 10.8422C2.79478 11.0999 3.00372 11.3089 3.26145 11.3089L10.7281 11.3089C10.9858 11.3089 11.1948 11.0999 11.1948 10.8422L11.1948 5.24219C11.1948 4.98445 10.9858 4.77552 10.7281 4.77552L9.56145 4.77552C9.30372 4.77552 9.09478 4.56659 9.09478 4.30885C9.09478 4.05112 9.30372 3.84219 9.56145 3.84219L10.7281 3.84219C11.5013 3.84219 12.1281 4.46899 12.1281 5.24219L12.1281 10.8422C12.1281 11.6154 11.5013 12.2422 10.7281 12.2422L3.26145 12.2422C2.48825 12.2422 1.86145 11.6154 1.86145 10.8422L1.86145 5.24219C1.86145 4.46899 2.48825 3.84219 3.26145 3.84219L4.42812 3.84219C4.68585 3.84219 4.89478 4.05112 4.89478 4.30885C4.89478 4.56659 4.68585 4.77552 4.42812 4.77552L3.26145 4.77552ZM6.52942 1.63841L6.52942 8.04208C6.52942 8.29981 6.73835 8.50874 6.99609 8.50874C7.25382 8.50874 7.46275 8.29981 7.46275 8.04208L7.46275 1.63372L8.80144 2.97242C8.96546 3.13644 9.23139 3.13644 9.39541 2.97242C9.55943 2.8084 9.55943 2.54247 9.39541 2.37845L7.29541 0.278446C7.21665 0.199681 7.10982 0.155431 6.99843 0.155431C6.88704 0.155431 6.78021 0.199681 6.70144 0.278446L4.60144 2.37845C4.43742 2.54247 4.43742 2.8084 4.60144 2.97242C4.76546 3.13644 5.03139 3.13644 5.19541 2.97242L6.52942 1.63841Z"
                      fill="#B3B3B3"
                    />
                  </svg>
                </p>
                <p className="ant-upload-text leading-[100%] mb-[.1rem]">
                  {props.text}
                </p>
                <p className="ant-upload-hint">{props.hint}</p>
              </div>
            ) : (
              <p className="ant-upload-text">
                {fileList.map((file) => (
                  <div
                    key={file.uid}
                    className="flex items-center gap-[.5rem] justify-center"
                  >
                    <svg
                      width="0.875rem"
                      height="0.875rem"
                      viewBox="0 0 14 15"
                      fill="none"
                      xmlns="http://www.w3.org/2000/svg"
                    >
                      <path
                        fillRule="evenodd"
                        clipRule="evenodd"
                        d="M3.26145 4.77552C3.00372 4.77552 2.79478 4.98445 2.79478 5.24219L2.79478 10.8422C2.79478 11.0999 3.00372 11.3089 3.26145 11.3089L10.7281 11.3089C10.9858 11.3089 11.1948 11.0999 11.1948 10.8422L11.1948 5.24219C11.1948 4.98445 10.9858 4.77552 10.7281 4.77552L9.56145 4.77552C9.30372 4.77552 9.09478 4.56659 9.09478 4.30885C9.09478 4.05112 9.30372 3.84219 9.56145 3.84219L10.7281 3.84219C11.5013 3.84219 12.1281 4.46899 12.1281 5.24219L12.1281 10.8422C12.1281 11.6154 11.5013 12.2422 10.7281 12.2422L3.26145 12.2422C2.48825 12.2422 1.86145 11.6154 1.86145 10.8422L1.86145 5.24219C1.86145 4.46899 2.48825 3.84219 3.26145 3.84219L4.42812 3.84219C4.68585 3.84219 4.89478 4.05112 4.89478 4.30885C4.89478 4.56659 4.68585 4.77552 4.42812 4.77552L3.26145 4.77552ZM6.52942 1.63841L6.52942 8.04208C6.52942 8.29981 6.73835 8.50874 6.99609 8.50874C7.25382 8.50874 7.46275 8.29981 7.46275 8.04208L7.46275 1.63372L8.80144 2.97242C8.96546 3.13644 9.23139 3.13644 9.39541 2.97242C9.55943 2.8084 9.55943 2.54247 9.39541 2.37845L7.29541 0.278446C7.21665 0.199681 7.10982 0.155431 6.99843 0.155431C6.88704 0.155431 6.78021 0.199681 6.70144 0.278446L4.60144 2.37845C4.43742 2.54247 4.43742 2.8084 4.60144 2.97242C4.76546 3.13644 5.03139 3.13644 5.19541 2.97242L6.52942 1.63841Z"
                        fill="#B3B3B3"
                      />
                    </svg>
                    <div key={file.uid}>{file.name}</div>
                  </div>
                ))}
              </p>
            )}
          </Dragger>
        </FloatLabel>
      </div>
    </Form.Item>
  );
};

export default FileInput;
