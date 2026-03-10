"use client";

import React, { useCallback, useEffect, useMemo, useState } from "react";
import { Drawer, Input } from "antd";
import {
  Text_14_400_EEEEEE,
  Text_12_400_B3B3B3,
  Text_12_400_757575,
} from "@/components/ui/text";
import { PrimaryButton, SecondaryButton } from "@/components/ui/bud/form/Buttons";
import CustomSelect from "src/flows/components/CustomSelect";
import { useGlobalConnectors } from "@/stores/useGlobalConnectors";
import { GlobalConnectorService } from "@/services/globalConnectorService";
import type { CredentialSchemaField, KeyValuePair } from "@/stores/useConnectors";

// ---------------------------------------------------------------------------
// Key-value-array helpers (same as settings/connectors/index.tsx)
// ---------------------------------------------------------------------------

const DEFAULT_KEY_VALUE_PAIR: KeyValuePair = { key: "", value: "Bearer " };

const parseKeyValueArray = (value: string | undefined): KeyValuePair[] => {
  if (!value) return [{ ...DEFAULT_KEY_VALUE_PAIR }];
  try {
    const parsed = JSON.parse(value);
    if (Array.isArray(parsed) && parsed.length > 0) return parsed;
    return [{ ...DEFAULT_KEY_VALUE_PAIR }];
  } catch {
    return [{ ...DEFAULT_KEY_VALUE_PAIR }];
  }
};

const stringifyKeyValueArray = (pairs: KeyValuePair[]): string =>
  JSON.stringify(pairs);

const REDIRECT_URI_FIELDS = ["redirect_uri", "redirect_url", "callback_url"];
const isRedirectUriField = (fieldName: string) =>
  REDIRECT_URI_FIELDS.includes(fieldName.toLowerCase());

// ---------------------------------------------------------------------------
// Icons
// ---------------------------------------------------------------------------

const PlusIcon = () => (
  <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
    <path d="M12 5v14" />
    <path d="M5 12h14" />
  </svg>
);

// ---------------------------------------------------------------------------
// Auth type options
// ---------------------------------------------------------------------------

const AUTH_TYPE_OPTIONS = [
  { label: "None", value: "Open" },
  { label: "Headers", value: "Headers" },
  { label: "OAuth", value: "OAuth" },
];

const TRANSPORT_OPTIONS = [
  { label: "STREAMABLEHTTP", value: "STREAMABLEHTTP" },
  { label: "SSE", value: "SSE" },
];

// ---------------------------------------------------------------------------
// ConnectMCPDrawer
// ---------------------------------------------------------------------------

interface ConnectMCPDrawerProps {
  open: boolean;
  onClose: () => void;
  onSuccess: () => void;
}

const ConnectMCPDrawer: React.FC<ConnectMCPDrawerProps> = ({ open, onClose, onSuccess }) => {
  const { createCustomGateway } = useGlobalConnectors();

  // Form state
  const [name, setName] = useState("");
  const [url, setUrl] = useState("");
  const [description, setDescription] = useState("");
  const [transport, setTransport] = useState("STREAMABLEHTTP");
  const [authType, setAuthType] = useState("Open");
  const [credentialForm, setCredentialForm] = useState<Record<string, string>>({});
  const [credentialSchemaMap, setCredentialSchemaMap] = useState<Record<string, CredentialSchemaField[]>>({});
  const [isSubmitting, setIsSubmitting] = useState(false);

  // Responsive drawer width
  const [drawerWidth, setDrawerWidth] = useState(400);
  useEffect(() => {
    if (typeof window === "undefined") return;
    const handleResize = () => {
      const sw = window.innerWidth;
      if (sw > 2560) setDrawerWidth(sw * 0.35);
      else if (sw > 1920) setDrawerWidth(sw * 0.4322);
      else if (sw > 1280) setDrawerWidth(sw * 0.433);
      else if (sw > 1024) setDrawerWidth(450);
      else setDrawerWidth(400);
    };
    handleResize();
    window.addEventListener("resize", handleResize);
    return () => window.removeEventListener("resize", handleResize);
  }, []);

  // Fetch credential schema on mount
  useEffect(() => {
    GlobalConnectorService.getCustomCredentialSchema()
      .then((res) => {
        if (res?.data?.schema) {
          setCredentialSchemaMap(res.data.schema);
        }
      })
      .catch(() => {});
  }, []);

  // Reset form when drawer closes
  useEffect(() => {
    if (!open) {
      setName("");
      setUrl("");
      setDescription("");
      setTransport("STREAMABLEHTTP");
      setAuthType("Open");
      setCredentialForm({});
      setIsSubmitting(false);
    }
  }, [open]);

  // Current credential fields for selected auth type
  const credentialFields = useMemo<CredentialSchemaField[]>(
    () => (credentialSchemaMap[authType] as CredentialSchemaField[]) || [],
    [credentialSchemaMap, authType],
  );

  // Reset credential form when auth type changes
  useEffect(() => {
    const initialForm: Record<string, string> = {};
    for (const field of credentialFields) {
      initialForm[field.field] = field.default || "";
    }
    setCredentialForm(initialForm);
  }, [credentialFields]);

  // Filter fields based on visible_when
  const visibleFields = useMemo(() => {
    const grantTypeValue = credentialForm["grant_type"];
    return credentialFields.filter((field) => {
      if (!field.visible_when || field.visible_when.length === 0) return true;
      return grantTypeValue && field.visible_when.includes(grantTypeValue);
    });
  }, [credentialFields, credentialForm]);

  // Auto-populate redirect URI
  useEffect(() => {
    if (typeof window === "undefined") return;
    setCredentialForm((prev) => {
      const updated = { ...prev };
      let changed = false;
      for (const field of visibleFields) {
        if (field.default && !updated[field.field]) {
          updated[field.field] = field.default;
          changed = true;
        }
      }
      const redirectField = visibleFields.find((f) => isRedirectUriField(f.field));
      if (redirectField && !updated[redirectField.field]) {
        updated[redirectField.field] = `${window.location.origin}/oauth/callback`;
        changed = true;
      }
      return changed ? updated : prev;
    });
  }, [visibleFields]);

  const handleCredentialChange = useCallback(
    (field: string, value: string) => {
      setCredentialForm((prev) => ({ ...prev, [field]: value }));
    },
    [],
  );

  const isFormValid = useMemo(() => {
    if (!name.trim() || !url.trim()) return false;
    if (!url.startsWith("http://") && !url.startsWith("https://")) return false;
    for (const field of visibleFields) {
      if (authType === "OAuth" && (field.field === 'client_id' || field.field === 'client_secret')) continue;
      if (field.required && !credentialForm[field.field]?.trim()) return false;
    }
    return true;
  }, [name, url, authType, visibleFields, credentialForm]);

  // Submit
  const handleSubmit = useCallback(async () => {
    setIsSubmitting(true);

    // Transform credentials (same logic as settings/connectors handleSubmitCredentials)
    const credentials: Record<string, any> = {};
    const fieldTypeMap = new Map<string, string>();
    credentialFields.forEach((f) => fieldTypeMap.set(f.field, f.type));

    for (const [key, value] of Object.entries(credentialForm)) {
      const fieldType = fieldTypeMap.get(key);
      if (fieldType === "key-value-array") {
        if (value) {
          try {
            const parsed = JSON.parse(value);
            if (Array.isArray(parsed)) {
              credentials[key] = parsed.filter(
                (p: any) => p?.key?.trim() || p?.value?.trim(),
              );
            }
          } catch {
            // skip parse errors
          }
        }
      } else if (key === "passthrough_headers" || key === "scopes") {
        if (value) {
          credentials[key] = value.split(",").map((s: string) => s.trim()).filter(Boolean);
        }
      } else {
        credentials[key] = value;
      }
    }

    const success = await createCustomGateway({
      name: name.trim(),
      url: url.trim(),
      description: description.trim() || undefined,
      transport: transport || undefined,
      credentials,
    });

    setIsSubmitting(false);

    if (success) {
      onSuccess();
    }
  }, [name, url, description, transport, credentialForm, credentialFields, createCustomGateway, onSuccess]);

  // Credential field renderer (duplicated from settings/connectors/index.tsx pattern)
  const renderCredentialField = (field: CredentialSchemaField) => {
    const inputClassName =
      "border border-[#757575] rounded-[6px] placeholder:text-[#757575] text-[#EEEEEE] bg-[transparent] py-[0.15rem] px-[.4rem] w-full";

    const isOptionalCred = authType === "OAuth" && (field.field === 'client_id' || field.field === 'client_secret');
    const renderLabel = () => (
      <div className="min-w-[9.375rem]">
        <Text_12_400_B3B3B3 className="text-nowrap">
          {field.label}
          {field.required && !isOptionalCred && <span className="text-[#E82E2E] ml-0.5">*</span>}
        </Text_12_400_B3B3B3>
      </div>
    );

    switch (field.type) {
      case "dropdown":
        return (
          <div key={field.field} className="w-full flex justify-between items-center gap-[.8rem]">
            {renderLabel()}
            <CustomSelect
              name={field.field}
              placeholder={field.label}
              value={credentialForm[field.field]}
              onChange={(value: string) => handleCredentialChange(field.field, value)}
              selectOptions={field.options?.map((opt) => ({
                label: opt.replace(/_/g, " "),
                value: opt,
              }))}
              InputClasses="!h-[1.9375rem] min-h-[1.9375rem] !text-[0.6875rem] !py-[.45rem]"
            />
          </div>
        );

      case "password":
        return (
          <div key={field.field} className="w-full flex justify-between items-center gap-[.8rem] relative">
            {renderLabel()}
            <Input
              type="password"
              placeholder={field.placeholder || field.label}
              value={credentialForm[field.field] || ""}
              onChange={(e) => handleCredentialChange(field.field, e.target.value)}
              className={`${inputClassName} pr-[1.5rem]`}
              autoComplete="new-password"
            />
          </div>
        );

      case "key-value-array": {
        const pairs = parseKeyValueArray(credentialForm[field.field]);

        const handlePairChange = (
          index: number,
          pairField: "key" | "value",
          newValue: string,
        ) => {
          const updatedPairs = [...pairs];
          updatedPairs[index] = { ...updatedPairs[index], [pairField]: newValue };
          handleCredentialChange(field.field, stringifyKeyValueArray(updatedPairs));
        };

        const handleAddPair = () => {
          const updatedPairs = [...pairs, { ...DEFAULT_KEY_VALUE_PAIR }];
          handleCredentialChange(field.field, stringifyKeyValueArray(updatedPairs));
        };

        const handleRemovePair = (index: number) => {
          if (pairs.length <= 1) {
            handleCredentialChange(field.field, stringifyKeyValueArray([{ ...DEFAULT_KEY_VALUE_PAIR }]));
            return;
          }
          const updatedPairs = pairs.filter((_, i) => i !== index);
          handleCredentialChange(field.field, stringifyKeyValueArray(updatedPairs));
        };

        return (
          <div key={field.field}>
            <Text_12_400_B3B3B3 className="text-nowrap mb-2">
              {field.label}
              {field.required && <span className="text-[#E82E2E] ml-0.5">*</span>}
            </Text_12_400_B3B3B3>
            <div className="space-y-3">
              {pairs.map((pair, index) => (
                <div
                  key={index}
                  className="relative p-[.5rem] rounded-[6px] bg-[#141414] border border-[#1F1F1F]"
                >
                  <button
                    type="button"
                    onClick={() => handleRemovePair(index)}
                    className="absolute top-2 right-1 flex items-center justify-center w-[1.25rem] h-[1.25rem] rounded-[.25rem] hover:bg-[#E82E2E1A] transition-colors"
                    title="Remove"
                  >
                    <svg xmlns="http://www.w3.org/2000/svg" width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" className="text-[#808080] hover:text-[#E82E2E]">
                      <path d="M18 6L6 18" />
                      <path d="M6 6l12 12" />
                    </svg>
                  </button>
                  <div className="space-y-2 pr-5">
                    <Input
                      placeholder="Key"
                      value={pair.key}
                      onChange={(e) => handlePairChange(index, "key", e.target.value)}
                      className={inputClassName}
                      autoComplete="off"
                    />
                    <Input
                      placeholder="Value"
                      value={pair.value}
                      onChange={(e) => handlePairChange(index, "value", e.target.value)}
                      className={inputClassName}
                      autoComplete="off"
                    />
                  </div>
                </div>
              ))}
              <button
                type="button"
                onClick={handleAddPair}
                className="flex items-center gap-1.5 px-3 py-1.5 rounded-[6px] border border-dashed border-[#2A2A2A] hover:border-[#965CDE] hover:bg-[#965CDE1A] transition-colors text-[#808080] hover:text-[#965CDE] text-[0.6875rem]"
              >
                <PlusIcon />
                Add {field.label || "Header"}
              </button>
            </div>
          </div>
        );
      }

      case "url":
      case "text":
      default:
        return (
          <div key={field.field} className="w-full flex justify-between items-center gap-[.8rem]">
            {renderLabel()}
            <Input
              placeholder={field.placeholder || field.label}
              value={credentialForm[field.field] || ""}
              onChange={(e) => handleCredentialChange(field.field, e.target.value)}
              className={inputClassName}
              autoComplete="off"
            />
          </div>
        );
    }
  };

  const inputClassName =
    "border border-[#757575] rounded-[6px] placeholder:text-[#757575] text-[#EEEEEE] bg-[transparent] py-[0.15rem] px-[.4rem] w-full";

  return (
    <>
      <Drawer
        title={null}
        placement="right"
        width={drawerWidth}
        open={open}
        onClose={onClose}
        closable={false}
        destroyOnClose
        styles={{ body: { padding: 0 }, header: { display: "none" } }}
        rootClassName="connect-mcp-drawer"
      >
        <div className="drawerBackground flex flex-col h-full">
          {/* Header */}
          <div className="ant-header-breadcrumb">
            <div className="flex items-center gap-2">
              <button onClick={onClose}>
                <svg width="18" height="18" viewBox="0 0 18 18" fill="none" xmlns="http://www.w3.org/2000/svg" className="hover:text-[#FFFFFF]">
                  <path fillRule="evenodd" clipRule="evenodd" d="M13.8103 5.09188C14.0601 4.8421 14.0601 4.43712 13.8103 4.18734C13.5606 3.93755 13.1556 3.93755 12.9058 4.18734L8.99884 8.0943L5.09188 4.18734C4.8421 3.93755 4.43712 3.93755 4.18734 4.18734C3.93755 4.43712 3.93755 4.8421 4.18734 5.09188L8.0943 8.99884L4.18734 12.9058C3.93755 13.1556 3.93755 13.5606 4.18734 13.8103C4.43712 14.0601 4.8421 14.0601 5.09188 13.8103L8.99884 9.90338L12.9058 13.8103C13.1556 14.0601 13.5606 14.0601 13.8103 13.8103C14.0601 13.5606 14.0601 13.1556 13.8103 12.9058L9.90338 8.99884L13.8103 5.09188Z" fill="#B3B3B3" />
                </svg>
              </button>
            </div>
          </div>

          {/* Scrollable content */}
          <div className="flex flex-col flex-1 overflow-hidden">
            <div className="BudWraperBox scrollBox py-[20px] overflow-y-auto h-full">
              {/* Connection Details card */}
              <div className="form-layout !mb-[1.1rem]">
                <div
                  className="px-[1.4rem] rounded-ss-lg rounded-se-lg border-b-[.5px] border-b-[#1F1F1F]"
                  style={{ paddingTop: "1.1rem", paddingBottom: ".9rem" }}
                >
                  <Text_14_400_EEEEEE className="p-0 pt-[.4rem] m-0">
                    Connect MCP
                  </Text_14_400_EEEEEE>
                  <div style={{ paddingTop: ".55rem" }}>
                    <Text_12_400_757575 className="leading-[180%]">
                      Connect to any MCP server by providing its URL
                    </Text_12_400_757575>
                  </div>
                </div>

                <div className="px-[1.4rem] flex flex-col gap-[1.25rem] pt-[1.1rem] pb-[1.5rem]">
                  {/* Name */}
                  <div className="w-full flex justify-between items-center gap-[.8rem]">
                    <div className="min-w-[9.375rem]">
                      <Text_12_400_B3B3B3 className="text-nowrap">
                        Name<span className="text-[#E82E2E] ml-0.5">*</span>
                      </Text_12_400_B3B3B3>
                    </div>
                    <Input
                      placeholder="My MCP Server"
                      value={name}
                      onChange={(e) => setName(e.target.value)}
                      className={inputClassName}
                      autoComplete="off"
                    />
                  </div>

                  {/* URL */}
                  <div className="w-full flex flex-col gap-[.3rem]">
                    <div className="flex justify-between items-center gap-[.8rem]">
                      <div className="min-w-[9.375rem]">
                        <Text_12_400_B3B3B3 className="text-nowrap">
                          URL<span className="text-[#E82E2E] ml-0.5">*</span>
                        </Text_12_400_B3B3B3>
                      </div>
                      <Input
                        placeholder="https://mcp.example.com/mcp"
                        value={url}
                        onChange={(e) => setUrl(e.target.value)}
                        className={inputClassName}
                        autoComplete="off"
                      />
                    </div>
                    <Text_12_400_757575 className="ml-[9.375rem] pl-[.8rem] leading-[150%]">
                      Include the full endpoint path (e.g. /mcp, /sse)
                    </Text_12_400_757575>
                  </div>

                  {/* Description */}
                  <div className="w-full flex justify-between items-start gap-[.8rem]">
                    <div className="min-w-[9.375rem] pt-[0.15rem]">
                      <Text_12_400_B3B3B3 className="text-nowrap">Description</Text_12_400_B3B3B3>
                    </div>
                    <Input.TextArea
                      placeholder="Optional description"
                      value={description}
                      onChange={(e) => setDescription(e.target.value)}
                      className={inputClassName}
                      autoSize={{ minRows: 2, maxRows: 4 }}
                      autoComplete="off"
                    />
                  </div>

                  {/* Transport */}
                  <div className="w-full flex justify-between items-center gap-[.8rem]">
                    <div className="min-w-[9.375rem]">
                      <Text_12_400_B3B3B3 className="text-nowrap">Transport</Text_12_400_B3B3B3>
                    </div>
                    <CustomSelect
                      name="transport"
                      placeholder="Auto-detect"
                      value={transport}
                      onChange={(value: string) => setTransport(value)}
                      selectOptions={TRANSPORT_OPTIONS}
                      InputClasses="!h-[1.9375rem] min-h-[1.9375rem] !text-[0.6875rem] !py-[.45rem]"
                    />
                  </div>
                </div>
              </div>

              {/* Authentication card */}
              <div className="form-layout !mb-[1.1rem]">
                <div
                  className="px-[1.4rem] rounded-ss-lg rounded-se-lg border-b-[.5px] border-b-[#1F1F1F]"
                  style={{ paddingTop: "1.1rem", paddingBottom: ".9rem" }}
                >
                  <Text_14_400_EEEEEE className="p-0 m-0">Authentication</Text_14_400_EEEEEE>
                </div>

                <div className="px-[1.4rem] flex flex-col gap-[1.25rem] pt-[1.1rem] pb-[1.5rem]">
                  {/* Auth Type */}
                  <div className="w-full flex justify-between items-center gap-[.8rem]">
                    <div className="min-w-[9.375rem]">
                      <Text_12_400_B3B3B3 className="text-nowrap">Auth Type</Text_12_400_B3B3B3>
                    </div>
                    <CustomSelect
                      name="authType"
                      placeholder="Open"
                      value={authType}
                      onChange={(value: string) => setAuthType(value)}
                      selectOptions={AUTH_TYPE_OPTIONS}
                      InputClasses="!h-[1.9375rem] min-h-[1.9375rem] !text-[0.6875rem] !py-[.45rem]"
                    />
                  </div>

                  {/* Dynamic credential fields */}
                  {visibleFields.length > 0 && (
                    <div className="flex flex-col gap-[1.25rem]">
                      {[...visibleFields]
                        .sort((a, b) => a.order - b.order)
                        .map((field) => renderCredentialField(field))}
                    </div>
                  )}
                </div>
              </div>
            </div>

            {/* Footer */}
            <div className="drawerFooter z-[5000] min-[4.1875rem] flex flex-col justify-start">
              <div
                style={{ justifyContent: "space-between" }}
                className="h-[4rem] pt-[.1rem] flex items-center px-[2.7rem]"
              >
                <SecondaryButton onClick={onClose}>Cancel</SecondaryButton>
                <PrimaryButton
                  onClick={handleSubmit}
                  loading={isSubmitting}
                  disabled={isSubmitting || !isFormValid}
                  style={{
                    cursor: isSubmitting || !isFormValid ? "not-allowed" : "pointer",
                    transform: "none",
                  }}
                >
                  {isSubmitting ? "Connecting..." : "Connect"}
                </PrimaryButton>
              </div>
            </div>
          </div>
        </div>
      </Drawer>

      <style jsx global>{`
        .connect-mcp-drawer .ant-drawer-content { background: transparent !important; }
        .connect-mcp-drawer .ant-drawer-body { background: transparent !important; }
      `}</style>
    </>
  );
};

export default ConnectMCPDrawer;
