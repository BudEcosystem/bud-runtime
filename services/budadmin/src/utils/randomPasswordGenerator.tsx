import React, { useState, useEffect, useCallback } from "react";
import { ReloadIcon } from "@radix-ui/react-icons";
import { Flex, TextField } from "@radix-ui/themes";

interface PasswordGeneratorProps {
  onPasswordChange: (password: string) => void;
}

const PasswordGenerator: React.FC<PasswordGeneratorProps> = ({
  onPasswordChange,
}) => {
  const makeId = (length: number, symbol: boolean) => {
    let result = "";
    let characters = symbol
      ? "ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789!@#$%^&*()_+"
      : "ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789";
    let charactersLength = characters.length;
    let hasDigit = false;
    let hasSpecialChar = false;
    const specialChars = "!@#$%^&*()_+";

    for (let i = 0; i < length; i++) {
      const char = characters.charAt(
        Math.floor(Math.random() * charactersLength)
      );
      result += char;

      // Check if the char is a digit
      if (/\d/.test(char)) {
        hasDigit = true;
      }

      // Check if the char is a special character
      if (specialChars.includes(char)) {
        hasSpecialChar = true;
      }
    }

    if (!hasDigit) {
      result += Math.floor(Math.random() * 10); // Append a digit between 0-9
    }
    if (!hasSpecialChar && symbol) {
      result += specialChars.charAt(
        Math.floor(Math.random() * specialChars.length)
      );
    }
    return result;
  };

  const [symbol, setSymbol] = useState(true); // Default to true to include symbols
  const [randomPassword, setRandomPassword] = useState("");
  const [length, setLength] = useState(10);
  const [isCopy, setIsCopy] = useState(false);

  const generatePassword = useCallback(() => {
    const newPassword = makeId(length, symbol);
    setRandomPassword(newPassword);
  }, [length, symbol]);

  const onGenerate = () => {
    setIsCopy(false);
    generatePassword();
  };

  const onChangePasswordLength = (e: React.ChangeEvent<HTMLInputElement>) => {
    const newValue = parseInt(e.target.value);
    setLength(newValue > 20 ? 20 : newValue);
  };

  const onIsSymbol = (checked: boolean) => {
    setSymbol(checked);
  };

  const onCopy = () => {
    setIsCopy(true);
  };

  useEffect(() => {
    onPasswordChange(randomPassword);
  }, [randomPassword, onPasswordChange]);

  useEffect(() => {
    generatePassword();
  }, [generatePassword]);

  return (
    <div className="pt-[.1rem]">
      <Flex justify="start" align="center">
        <TextField.Root
          disabled
          value={randomPassword}
          placeholder="password"
          className="w-[6rem] p-0 text-xs font-light border-0 shadow-none bg-[#111113] bg-none"
        />
        <button onClick={onGenerate} className="w-[0.625rem] h-[0.625rem] p-0">
          <ReloadIcon className="w-[0.625rem] h-[0.625rem]" />
        </button>
      </Flex>
      {/* <CopyToClipboard text={randomPassword}>
          <button
            disabled={randomPassword.length < 1}
            onClick={onCopy}
          >
            Copy
          </button>
        </CopyToClipboard>
        {isCopy ? (
          <label style={{ color: "red" }}> Copied</label>
        ) : (
          ""
        )} */}

      {/* <input
          style={{ marginBottom: "0.5rem" }}
          min="1"
          max="20"
          type="number"
          placeholder="1-20"
          value={length}
          onChange={onChangePasswordLength}
        /> */}
    </div>
  );
};

export default PasswordGenerator;
