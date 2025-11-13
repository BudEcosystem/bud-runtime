import React, { useCallback, useEffect, useState } from "react";
import {
  Dialog,
  Button,
  Text,
  TextField,
  Select,
  Flex,
  Box,
  Tooltip,
} from "@radix-ui/themes";
import { Cross1Icon } from "@radix-ui/react-icons";
import { AppRequest } from "src/pages/api/requests";
import { Value } from "@radix-ui/themes/dist/cjs/components/data-list";
import Image from "next/image";
import * as Checkbox from "@radix-ui/react-checkbox";
import { CheckIcon } from "@radix-ui/react-icons";
import globeIcn from "./../../../../../public/icons/Globe.png";
import copyIcn from "./../../../../../public/icons/copy.png";
import PasswordGenerator from "src/utils/randomPasswordGenerator";
import { copyToClipboard } from "@/utils/clipboard";
import { CopyToClipboard } from "react-copy-to-clipboard";
import { Text_12_400_6A6E76 } from "@/components/ui/text";

interface GeneratePassPopupProps {
  isOpen: boolean;
  onOpenChange: (isOpen: boolean) => void;
  title: string;
  description: string;
  initialValues?: ""; // Optional initial values for edit functionality
  onSubmit: (formData: { [key: string]: string }) => void;
}

const GeneratePassPopup: React.FC<GeneratePassPopupProps> = ({
  isOpen,
  onOpenChange,
  title,
  description,
  initialValues = "", // Default to empty object
  onSubmit,
}) => {
  const [formData, setFormData] = React.useState<{ [key: string]: string }>({});
  const [editFormData, setEditFormData] = React.useState<{
    [key: string]: string;
  }>({});
  const [userData, setUserData] = useState<any>();
  const [userName, setUserName] = useState("");
  const [userEmail, setUserEmail] = useState("");
  const [userChr, setUserChr] = useState("");
  const [projectList, setProjectList] = useState<any>(null);
  const [projectId, setprojectId] = useState("");
  const [generatedPassword, setGeneratedPassword] = useState("");
  const [adminMessage, setAdminMessage] = useState("message");
  const [isCopy, setIsCopy] = useState(false);
  const [copyMessage, setCopyMessage] = useState<any>("click to copy");

  const [userPermissions, setUserPermissions] = useState<any>(null);
  const [selectedValue, setSelectedValue] = useState<any>({});
  const [checked, setChecked] = useState<any>(false);

  const [currentPage, setCurrentPage] = useState(1);
  const [pageSize, setPageSize] = useState(100);
  const totalItems = 100;
  const options = [
    { label: "View", value: "true" },
    { label: "Edit", value: "true" },
    { label: "No access", value: "false" },
  ];
  const getUser = useCallback(async () => {
    if (!initialValues || !isOpen) return;
    try {
      const response: any = await AppRequest.Get(`/users/${initialValues}`);
      let getData = response.data.result;
      const abv: string = getData?.name[0] + getData?.name[1];
      const name: string =
        getData?.name.charAt(0).toUpperCase() + getData?.name.slice(1);
      setUserData(getData);
      setUserName(name);
      setUserEmail(getData?.email);
      setUserChr(abv.toUpperCase());
    } catch (error) {
      console.error("Error getting user:", error);
    }
  }, [initialValues]);

  const getUserPermissions = useCallback(async () => {
    if (!initialValues || !isOpen) return;
    try {
      const response: any = await AppRequest.Get(
        `/permissions/${initialValues}`,
      );
      let permission = response.data.result;
      let result = {};
      for (let i = 0; i < permission.length; i++) {
        let permissionItem = permission[i];
        let key = permissionItem["name"].replace(":", ""); // Remove ':' from permission name
        result[key] = permissionItem["has_permission"];
      }
      setUserPermissions(result);
    } catch (error) {
      console.error("Error creating model:", error);
    }
  }, [initialValues]);

  const getProjects = async (page: any, limit: any) => {
    try {
      const response: any = await AppRequest.Get(
        `/projects/?page=${page}&limit=${limit}&search=false`,
      );
      setProjectList(response.data.results);
    } catch (error) {
      console.error("Error creating model:", error);
    }
  };

  const handleChange = (key, value) => {
    setSelectedValue((prevPermissions: any) => ({
      ...prevPermissions,
      [key]: value,
    }));
  };

  useEffect(() => {
    if (isOpen) {
      setEditFormData({}); // Reset editFormData
    }
  }, [isOpen]);

  const handleSubmit = () => {
    onSubmit({
      password: generatedPassword,
      userEmail: userEmail,
    });
  };
  const handlePasswordChange = (password: string) => {
    setGeneratedPassword(password);
    setAdminMessage(`
      Admin has reset your password. Below are your details:

      New Password: ${password}
      Username: ${userEmail}

      Click this link to login: https://bud.studio`);
  };
  const onCopy = async () => {
    await copyToClipboard(adminMessage, {
      onSuccess: () => {
        setIsCopy(true);
        setCopyMessage("Copied..");
        setTimeout(() => {
          setCopyMessage("click to copy");
          setIsCopy(false);
        }, 10000);
      },
      onError: () => {
        setCopyMessage("Failed to copy");
      },
    });
  };
  useEffect(() => {
    if (initialValues) {
      getUser();
      getUserPermissions();
      getProjects(currentPage, pageSize);
    }
  }, [initialValues, currentPage, pageSize, getUser, getUserPermissions]);
  // const textFields = fields.filter(field => field.type === 'text');
  // const selectFields = fields.filter(field => field.type === 'select');
  // const editFields = fields.filter(field => field.name === 'name' || field.name === 'uri');
  // const nonEditFields = fields.filter(field => field.name !== 'name' && field.name !== 'uri');

  return (
    <Dialog.Root open={isOpen} onOpenChange={onOpenChange}>
      <Dialog.Content
        maxWidth="370px"
        className="w-[29%] p-[0.75rem] bg-[#111113] border-0 shadow-none"
      >
        <Box className="px-2">
          <Flex justify="between" align="center">
            <Dialog.Title className="text-base block p-0 pt-1 m-0">
              {title}
            </Dialog.Title>
            <Dialog.Close>
              <Button
                className="m-0 p-0 pt-[.1rem] bg-[transparent] h-[1.1rem]"
                size="1"
              >
                <Cross1Icon />
              </Button>
            </Dialog.Close>
          </Flex>
          <Dialog.Description className="text-xs text-[#44474D] pt-2" mb="3">
            {description}
          </Dialog.Description>
          <Flex
            className="profileDetails bg-[transparent] rounded-lg cursor-pointer"
            justify="start"
            align="center"
          >
            <Box
              className="rounded rounded-full border border-[#FBF3F3] border-[.5px] w-[1.25rem] h-[1.25rem]"
              style={{ backgroundColor: userData?.["color"] }}
            ></Box>
            <Box className="userName">
              <Text_12_400_6A6E76 className="">{userEmail}</Text_12_400_6A6E76>
            </Box>
          </Flex>
          <Box className="py-2">
            <Text className="text-xs text-[#787B83] font-normal	">
              Auto generated password
            </Text>
            <PasswordGenerator onPasswordChange={handlePasswordChange} />
          </Box>
          <Text className="text-xs text-[#44474D] font-light">
            Copy the message below and send it to the user.
          </Text>
          <Box className="adminMessage p-3 pb-4 mt-3 bg-[#18191B] rounded-lg text-[#FFFFFF]">
            <Flex align="start" justify="between">
              <Text
                as="div"
                className="text-xs font-light text-[#C7C7C7]"
                mb="1"
                weight="bold"
              >
                Admin has reset your password <br />
                Below are your details
              </Text>
              {/* <CopyToClipboard text={adminMessage}> */}
              <Tooltip
                content={copyMessage}
                className="text-xs"
                disableHoverableContent={true}
              >
                <button onClick={onCopy} className="mt-[.2em]">
                  <Image
                    width={20}
                    className="w-3.5 h-3.5"
                    src={copyIcn}
                    alt="Logo"
                  />
                </button>
              </Tooltip>
              {/* </CopyToClipboard> */}
            </Flex>
            <Box className="mt-3">
              <Text className="font-normal text-xs block">New Password:</Text>
              <Text className="font-light text-xs block">
                {generatedPassword}
              </Text>
            </Box>
            <Box className="mt-3">
              <Text className="font-normal text-xs block">Username:</Text>
              <Text className="font-light text-xs block">{userEmail}</Text>
            </Box>
            <Box className="mt-3">
              <Text className="font-normal text-xs">
                Click this link login:{" "}
              </Text>
              <Text className="font-light text-xs">
                <a>https://bud.studio</a>
              </Text>
            </Box>
          </Box>
        </Box>
        <Flex gap="3" mt="4" justify="center">
          <Button
            size="1"
            className="h-[1.75rem] w-full text-xs font-normal"
            onClick={handleSubmit}
            disabled={!isCopy}
          >
            Done
          </Button>
        </Flex>
      </Dialog.Content>
    </Dialog.Root>
  );
};

export default GeneratePassPopup;
