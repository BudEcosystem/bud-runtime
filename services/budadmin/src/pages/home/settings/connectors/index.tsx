"use client";

import React, { useCallback, useEffect, useMemo, useState } from "react";
import { Input, Drawer, Spin } from "antd";
import {
  Text_14_400_757575,
  Text_12_400_757575,
  Text_14_400_EEEEEE,
  Text_12_400_B3B3B3,
  Text_17_600_FFFFFF,
  Text_13_400_B3B3B3,
} from "@/components/ui/text";
import { PrimaryButton, SecondaryButton } from "@/components/ui/bud/form/Buttons";
import { useLoader } from "src/context/appContext";

import {
  useGlobalConnectors,
  type RegistryConnector,
  type ConfiguredConnector,
} from "@/stores/useGlobalConnectors";
import { CredentialSchemaField, KeyValuePair } from "@/stores/useConnectors";
import CustomSelect from "src/flows/components/CustomSelect";
import ProjectTags from "src/flows/components/ProjectTags";

// ---------------------------------------------------------------------------
// Tag color mapping for connector metadata
// ---------------------------------------------------------------------------
const AUTH_TYPE_COLORS: Record<string, string> = {
  oauth2: "#8B5CF6",
  "oauth2.1": "#8B5CF6",
  oauth2_1: "#8B5CF6",
  oauth: "#8B5CF6",
  api_key: "#F59E0B",
  headers: "#F59E0B",
  "oauth2_1_&_api_key": "#D97706",
  open: "#22C55E",
  none: "#808080",
};

function getAuthTypeColor(authType: string): string {
  const key = authType.toLowerCase().replace(/[\s.]/g, "_");
  return AUTH_TYPE_COLORS[key] || "#808080";
}

// Deterministic color from tag string (consistent across renders)
const TAG_PALETTE = [
  "#3B82F6", "#22C55E", "#F59E0B", "#EC4899", "#06B6D4",
  "#8B5CF6", "#EF4444", "#10B981", "#6366F1", "#D97706",
  "#F472B6", "#14B8A6", "#A855F7", "#FB923C",
];
function getTagColor(tag: string): string {
  let hash = 0;
  for (let i = 0; i < tag.length; i++) {
    hash = tag.charCodeAt(i) + ((hash << 5) - hash);
  }
  return TAG_PALETTE[Math.abs(hash) % TAG_PALETTE.length];
}

// ---------------------------------------------------------------------------
// Icons (inline SVGs)
// ---------------------------------------------------------------------------

const PlusIcon = () => (
  <svg
    width="14"
    height="14"
    viewBox="0 0 24 24"
    fill="none"
    stroke="currentColor"
    strokeWidth="2"
    strokeLinecap="round"
    strokeLinejoin="round"
  >
    <path d="M12 5v14" />
    <path d="M5 12h14" />
  </svg>
);

const LinkIcon = () => (
  <svg
    width="12"
    height="12"
    viewBox="0 0 24 24"
    fill="none"
    stroke="currentColor"
    strokeWidth="2"
    strokeLinecap="round"
    strokeLinejoin="round"
  >
    <path d="M10 13a5 5 0 0 0 7.54.54l3-3a5 5 0 0 0-7.07-7.07l-1.72 1.71" />
    <path d="M14 11a5 5 0 0 0-7.54-.54l-3 3a5 5 0 0 0 7.07 7.07l1.71-1.71" />
  </svg>
);

const ConnectorFallbackIcon = () => (
  <svg
    width="16"
    height="16"
    viewBox="0 0 24 24"
    fill="none"
    stroke="#965CDE"
    strokeWidth="2"
    strokeLinecap="round"
    strokeLinejoin="round"
  >
    <path d="M12 2L2 7l10 5 10-5-10-5z" />
    <path d="M2 17l10 5 10-5" />
    <path d="M2 12l10 5 10-5" />
  </svg>
);

// ---------------------------------------------------------------------------
// Helper: redirect URI auto-detection (mirrors ConnectorDetails.tsx)
// ---------------------------------------------------------------------------

const REDIRECT_URI_FIELDS = ['redirect_uri', 'redirect_url', 'callback_url'];
const isRedirectUriField = (fieldName: string) =>
  REDIRECT_URI_FIELDS.includes(fieldName.toLowerCase());

// ---------------------------------------------------------------------------
// Helper: key-value-array field support (mirrors CredentialConfigStep)
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

// ---------------------------------------------------------------------------
// Helper: match a registry connector to configured connectors via tag
// ---------------------------------------------------------------------------

interface ConnectorWithStatus extends RegistryConnector {
  isConnected: boolean;
  matchedGateway: ConfiguredConnector | null;
}

/**
 * Build a lookup map from configured connectors for efficient matching.
 * Uses the `connector_id` field from the configured connector (extracted
 * from the `connector-id:*` tag on the gateway) to match against registry.
 */
function buildConnectorStatusList(
  registryConnectors: RegistryConnector[],
  configured: ConfiguredConnector[],
): ConnectorWithStatus[] {
  const configuredMap = new Map<string, ConfiguredConnector>();
  for (const cc of configured) {
    // First match wins — if multiple gateways share the same connector_id
    if (!configuredMap.has(cc.connector_id)) {
      configuredMap.set(cc.connector_id, cc);
    }
  }

  return registryConnectors.map((connector) => {
    const matched = configuredMap.get(connector.id) || null;
    return {
      ...connector,
      isConnected: matched !== null,
      matchedGateway: matched,
    };
  });
}

// ---------------------------------------------------------------------------
// Main component: Connectors
// ---------------------------------------------------------------------------

interface ConnectorsProps {
  searchTerm?: string;
  onSearchChange?: (value: string) => void;
}

const Connectors: React.FC<ConnectorsProps> = ({ searchTerm: externalSearchTerm, onSearchChange }) => {
  const {
    configuredConnectors,
    configuredLoading,
    registryConnectors,
    registryTotal,
    registryLoading,
    fetchConfigured,
    fetchRegistry,
    configureConnector,
  } = useGlobalConnectors();
  const { isLoading: globalLoading } = useLoader();

  // ---- Local state --------------------------------------------------------
  const searchTerm = externalSearchTerm ?? "";
  const registryPageSize = 20;
  const registryPageRef = React.useRef(1);
  const isLoadingMoreRef = React.useRef(false);
  const loadMoreRef = React.useRef<HTMLDivElement>(null);

  // Credential drawer
  const [drawerOpen, setDrawerOpen] = useState(false);
  const [selectedConnector, setSelectedConnector] = useState<RegistryConnector | null>(null);
  const [credentialForm, setCredentialForm] = useState<Record<string, string>>({});
  const [isSubmitting, setIsSubmitting] = useState(false);

  // ---- Responsive drawer width (matches BudDrawer pattern) ----------------
  const drawerWidth = useMemo(() => {
    const screenWidth = typeof window !== 'undefined' ? window.innerWidth : 1440;
    if (screenWidth > 2560) return screenWidth * 0.35;
    if (screenWidth > 1920) return screenWidth * 0.4322;
    if (screenWidth > 1280) return screenWidth * 0.433;
    if (screenWidth > 1024) return 450;
    return 400;
  }, []);

  // ---- Computed values (needed before effects) ----------------------------
  const hasMore = registryConnectors.length < registryTotal;
  const isLoading = registryLoading && registryConnectors.length === 0;

  // ---- Load both registry and configured on mount -------------------------
  useEffect(() => {
    fetchRegistry({ page: 1, limit: registryPageSize });
    fetchConfigured({ include_disabled: true });
  }, []); // eslint-disable-line react-hooks/exhaustive-deps

  // Reset page ref when search term changes (parent triggers new search)
  useEffect(() => {
    registryPageRef.current = 1;
    isLoadingMoreRef.current = false;
  }, [searchTerm]);

  // Infinite scroll with IntersectionObserver (mirrors tools page)
  useEffect(() => {
    if (!loadMoreRef.current) return;

    const observer = new IntersectionObserver(
      (entries) => {
        const [entry] = entries;
        if (entry.isIntersecting && hasMore && !isLoadingMoreRef.current && !registryLoading) {
          isLoadingMoreRef.current = true;
          const nextPage = registryPageRef.current + 1;
          registryPageRef.current = nextPage;
          fetchRegistry({ name: searchTerm, page: nextPage, limit: registryPageSize }, true).finally(
            () => { isLoadingMoreRef.current = false; },
          );
        }
      },
      { root: null, rootMargin: "100px", threshold: 0.1 },
    );

    observer.observe(loadMoreRef.current);
    return () => observer.disconnect();
  }, [hasMore, registryLoading, searchTerm, fetchRegistry]);

  // ---- Build merged list with connection status --------------------------
  const connectorsWithStatus = useMemo<ConnectorWithStatus[]>(
    () => buildConnectorStatusList(registryConnectors, configuredConnectors),
    [registryConnectors, configuredConnectors],
  );

  // ---- Select a registry connector (open credential drawer) ---------------
  const handleConfigure = useCallback(
    (connector: RegistryConnector) => {
      const initialForm: Record<string, string> = {};
      if (connector.credential_schema) {
        for (const field of connector.credential_schema) {
          initialForm[field.field] = "";
        }
      }
      setSelectedConnector(connector);
      setCredentialForm(initialForm);
      setDrawerOpen(true);
    },
    [],
  );

  // ---- Credential form helpers --------------------------------------------
  const handleCredentialChange = useCallback(
    (field: string, value: string) => {
      setCredentialForm((prev) => ({ ...prev, [field]: value }));
    },
    [],
  );

  const credentialSchema = useMemo<CredentialSchemaField[]>(
    () => (selectedConnector?.credential_schema as CredentialSchemaField[]) || [],
    [selectedConnector],
  );

  /** Filter fields based on visible_when (e.g., grant_type-dependent fields) */
  const visibleFields = useMemo(() => {
    const grantTypeValue = credentialForm["grant_type"];
    return credentialSchema.filter((field) => {
      if (!field.visible_when || field.visible_when.length === 0) return true;
      return grantTypeValue && field.visible_when.includes(grantTypeValue);
    });
  }, [credentialSchema, credentialForm]);

  // Auto-populate redirect URI with the /agents page URL (where useOAuthCallback runs)
  useEffect(() => {
    if (typeof window === "undefined" || !selectedConnector?.credential_schema) return;

    const redirectField = visibleFields.find((f) => isRedirectUriField(f.field));
    if (redirectField) {
      const callbackUrl = `${window.location.origin}/oauth/callback`;
      setCredentialForm((prev) => {
        if (!prev[redirectField.field]) {
          return { ...prev, [redirectField.field]: callbackUrl };
        }
        return prev;
      });
    }
  }, [selectedConnector?.credential_schema, visibleFields]);

  const isFormValid = useMemo(() => {
    for (const field of visibleFields) {
      if (field.required && !credentialForm[field.field]?.trim()) {
        return false;
      }
    }
    return true;
  }, [visibleFields, credentialForm]);

  // ---- Close credential drawer -------------------------------------------
  const closeDrawer = useCallback(() => {
    setDrawerOpen(false);
    setSelectedConnector(null);
    setCredentialForm({});
  }, []);

  // ---- Submit credentials ------------------------------------------------
  const handleSubmitCredentials = useCallback(async () => {
    if (!selectedConnector) return;
    setIsSubmitting(true);

    // Transform flat form values into proper types for the backend
    const credentials: Record<string, any> = {};
    const fieldTypeMap = new Map<string, string>();
    (selectedConnector.credential_schema || []).forEach((f: CredentialSchemaField) => {
      fieldTypeMap.set(f.field, f.type);
    });

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
          } catch (e) {
            console.error(`Failed to parse key-value-array for field '${key}':`, value, e);
          }
        }
      } else if (key === "passthrough_headers" || key === "scopes") {
        if (value) {
          credentials[key] = value
            .split(",")
            .map((s: string) => s.trim())
            .filter(Boolean);
        }
      } else {
        credentials[key] = value;
      }
    }

    const success = await configureConnector(selectedConnector.id, credentials);
    setIsSubmitting(false);

    if (success) {
      closeDrawer();
      // Refresh configured connectors to update connection status
      fetchConfigured({ include_disabled: true });
    }
  }, [selectedConnector, credentialForm, configureConnector, closeDrawer, fetchConfigured]);


  // ---- Credential form field renderer (matches Add Credentials drawer) ----
  const renderCredentialField = (field: CredentialSchemaField) => {
    const inputClassName =
      "border border-[#757575] rounded-[6px] placeholder:text-[#757575] text-[#EEEEEE] bg-[transparent] py-[0.15rem] px-[.4rem] w-full";

    const renderLabel = () => (
      <div className="min-w-[9.375rem]">
        <Text_12_400_B3B3B3 className="text-nowrap">
          {field.label}
          {field.required && <span className="text-[#E82E2E] ml-0.5">*</span>}
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
              onChange={(value) => handleCredentialChange(field.field, value)}
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
              placeholder={field.label}
              value={credentialForm[field.field] || ""}
              onChange={(e) =>
                handleCredentialChange(field.field, e.target.value)
              }
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
          handleCredentialChange(
            field.field,
            stringifyKeyValueArray(updatedPairs),
          );
        };

        const handleAddPair = () => {
          const updatedPairs = [...pairs, { ...DEFAULT_KEY_VALUE_PAIR }];
          handleCredentialChange(
            field.field,
            stringifyKeyValueArray(updatedPairs),
          );
        };

        const handleRemovePair = (index: number) => {
          if (pairs.length <= 1) {
            handleCredentialChange(
              field.field,
              stringifyKeyValueArray([{ ...DEFAULT_KEY_VALUE_PAIR }]),
            );
            return;
          }
          const updatedPairs = pairs.filter((_, i) => i !== index);
          handleCredentialChange(
            field.field,
            stringifyKeyValueArray(updatedPairs),
          );
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
                    <svg
                      xmlns="http://www.w3.org/2000/svg"
                      width="12"
                      height="12"
                      viewBox="0 0 24 24"
                      fill="none"
                      stroke="currentColor"
                      strokeWidth="2"
                      strokeLinecap="round"
                      strokeLinejoin="round"
                      className="text-[#808080] hover:text-[#E82E2E]"
                    >
                      <path d="M18 6L6 18" />
                      <path d="M6 6l12 12" />
                    </svg>
                  </button>
                  <div className="space-y-2 pr-5">
                    <Input
                      placeholder="Key"
                      value={pair.key}
                      onChange={(e) =>
                        handlePairChange(index, "key", e.target.value)
                      }
                      className={inputClassName}
                      autoComplete="off"
                    />
                    <Input
                      placeholder="Value"
                      value={pair.value}
                      onChange={(e) =>
                        handlePairChange(index, "value", e.target.value)
                      }
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
              placeholder={field.label}
              value={credentialForm[field.field] || ""}
              onChange={(e) =>
                handleCredentialChange(field.field, e.target.value)
              }
              className={inputClassName}
              autoComplete="off"
            />
          </div>
        );
    }
  };

  // ---- Render -------------------------------------------------------------
  return (
    <div className="pb-[60px] pt-[.5rem] relative">
      {/* Registry connector grid */}
      {isLoading && !globalLoading ? (
        <div className="flex justify-center items-center py-20">
          <Spin size="default" />
        </div>
      ) : connectorsWithStatus.length === 0 ? (
        <div className="flex flex-col items-center justify-center py-20 gap-3">
          <svg
            width="40"
            height="40"
            viewBox="0 0 24 24"
            fill="none"
            stroke="#2A2A2A"
            strokeWidth="1.5"
            strokeLinecap="round"
            strokeLinejoin="round"
          >
            <rect x="2" y="2" width="20" height="8" rx="2" ry="2" />
            <rect x="2" y="14" width="20" height="8" rx="2" ry="2" />
            <line x1="6" y1="6" x2="6.01" y2="6" />
            <line x1="6" y1="18" x2="6.01" y2="18" />
          </svg>
          <Text_14_400_757575>
            {searchTerm
              ? "No connectors match your search."
              : "No connectors available in the registry."}
          </Text_14_400_757575>
        </div>
      ) : (
        <>
          <div className="grid gap-[1.1rem] grid-cols-3 mt-[1rem] pb-[1.1rem]">
            {connectorsWithStatus.map((connector) => (
              <div
                key={connector.id}
                className="flex flex-col justify-between bg-[#101010] border border-[#1F1F1F] rounded-lg min-h-[280px] 1680px:min-h-[320px] hover:shadow-[1px_1px_6px_-1px_#2e3036] overflow-hidden transition-all duration-200"
              >
                {/* Content area */}
                <div className="pr-[1.5em] pl-[1.5em] pt-[1.6em] h-full flex flex-col justify-start text-[1rem] 1680px:text-[1.1rem]">
                  {/* Icon */}
                  <div className="flex items-center justify-between">
                    {connector.icon ? (
                      <img
                        src={connector.icon}
                        alt=""
                        className="w-[2.40125rem] h-[2.40125rem] rounded flex-shrink-0 object-contain bg-[#1F1F1F] p-1"
                      />
                    ) : (
                      <div className="flex items-center justify-center bg-[#1F1F1F] w-[2.40125rem] h-[2.40125rem] rounded">
                        <ConnectorFallbackIcon />
                      </div>
                    )}
                  </div>

                  {/* Title */}
                  <Text_17_600_FFFFFF className="mt-[.85em] text-wrap pr-1 truncate-text max-w-[90%]">
                    {connector.name}
                  </Text_17_600_FFFFFF>

                  {/* Description */}
                  <Text_13_400_B3B3B3 className="pt-[.85em] pr-[.45em] text-[0.75em] tracking-[.01em] line-clamp-2 overflow-hidden leading-[150%]">
                    {connector.description || "No description available"}
                  </Text_13_400_B3B3B3>

                  {/* Tags */}
                  {(connector.tags?.length || connector.auth_type) && (
                    <div className="flex gap-[.45rem] justify-start items-center mt-[1.1rem] flex-wrap overflow-hidden mb-[1.1rem]" style={{ maxHeight: "4rem", lineHeight: "1.5rem" }}>
                      {connector.tags?.map((tag) => (
                        <ProjectTags
                          key={tag}
                          name={tag}
                          color={getTagColor(tag)}
                          textClass="text-[.625rem]"
                        />
                      ))}
                      {connector.auth_type && (
                        <ProjectTags
                          name={connector.auth_type.replace(/_/g, " ")}
                          color={getAuthTypeColor(connector.auth_type)}
                          textClass="text-[.625rem]"
                        />
                      )}
                    </div>
                  )}
                </div>

                {/* Footer */}
                <div className="flex items-center justify-between pt-[1.1rem] pr-[1.5em] pl-[1.5em] pb-[1.45em] bg-[#161616] border-t-[0.5px] border-t-[#1F1F1F]">
                  <div className="flex items-center gap-2">
                    {connector.documentation_url && (
                      <a
                        href={connector.documentation_url}
                        target="_blank"
                        rel="noopener noreferrer"
                        className="inline-flex items-center gap-1 text-[0.625rem] text-[#965CDE] hover:text-[#B07FEE] transition-colors"
                        onClick={(e) => e.stopPropagation()}
                      >
                        <LinkIcon />
                        Docs
                      </a>
                    )}
                  </div>
                  <PrimaryButton
                    onClick={() => handleConfigure(connector)}
                    classNames="h-[1.625rem] rounded-[0.3rem]"
                    textClass="!text-[0.6875rem] !font-[500]"
                  >
                    <span className="flex items-center gap-1 whitespace-nowrap">
                      <PlusIcon />
                      Configure
                    </span>
                  </PrimaryButton>
                </div>
              </div>
            ))}
          </div>

          {/* Infinite scroll sentinel + loading indicator */}
          {registryLoading && registryConnectors.length > 0 && (
            <div className="flex justify-center py-6">
              <Spin size="small" />
            </div>
          )}
          {hasMore && <div ref={loadMoreRef} className="h-1" />}
        </>
      )}

      {/* ---- Credential Form Drawer ---------------------------------------- */}
      <Drawer
        title={null}
        placement="right"
        width={drawerWidth}
        open={drawerOpen}
        onClose={closeDrawer}
        closable={false}
        destroyOnClose
        styles={{
          body: { padding: 0 },
          header: { display: "none" },
        }}
        rootClassName="connectors-drawer"
      >
        {/* drawerBackground: applies the global drawer background image */}
        <div className="drawerBackground flex flex-col h-full">
          {/* Header — matches ant-header-breadcrumb pattern */}
          <div className="ant-header-breadcrumb">
            <div className="flex items-center gap-2">
              <button onClick={closeDrawer}>
                <svg width="18" height="18" viewBox="0 0 18 18" fill="none" xmlns="http://www.w3.org/2000/svg" className="hover:text-[#FFFFFF]">
                  <path fillRule="evenodd" clipRule="evenodd" d="M13.8103 5.09188C14.0601 4.8421 14.0601 4.43712 13.8103 4.18734C13.5606 3.93755 13.1556 3.93755 12.9058 4.18734L8.99884 8.0943L5.09188 4.18734C4.8421 3.93755 4.43712 3.93755 4.18734 4.18734C3.93755 4.43712 3.93755 4.8421 4.18734 5.09188L8.0943 8.99884L4.18734 12.9058C3.93755 13.1556 3.93755 13.5606 4.18734 13.8103C4.43712 14.0601 4.8421 14.0601 5.09188 13.8103L8.99884 9.90338L12.9058 13.8103C13.1556 14.0601 13.5606 14.0601 13.8103 13.8103C14.0601 13.5606 14.0601 13.1556 13.8103 12.9058L9.90338 8.99884L13.8103 5.09188Z" fill="#B3B3B3" />
                </svg>
              </button>
            </div>
          </div>

          {/* Credential Form Content */}
          {selectedConnector && (
            <div className="flex flex-col flex-1 overflow-hidden">
              {/* Scrollable content wrapped in BudWraperBox-style container */}
              <div className="BudWraperBox scrollBox py-[20px] overflow-y-auto h-full">
                {/* form-layout card — matches global drawer card style */}
                <div className="form-layout !mb-[0]">
                  {/* Title card — matches DrawerTitleCard */}
                  <div
                    className="px-[1.4rem] rounded-ss-lg rounded-se-lg border-b-[.5px] border-b-[#1F1F1F]"
                    style={{ paddingTop: "1.1rem", paddingBottom: ".9rem" }}
                  >
                    <div className="flex justify-between align-center">
                      <Text_14_400_EEEEEE className="p-0 pt-[.4rem] m-0">
                        Configure Connector
                      </Text_14_400_EEEEEE>
                    </div>
                    <div style={{ paddingTop: ".55rem" }}>
                      <Text_12_400_757575 className="leading-[180%]">
                        Enter credentials below to configure {selectedConnector.name}
                      </Text_12_400_757575>
                    </div>
                  </div>

                  {/* Form fields */}
                  {credentialSchema.length === 0 ? (
                    <div className="flex flex-col items-center justify-center py-12 gap-2">
                      <Text_14_400_757575>
                        No credentials required for this connector.
                      </Text_14_400_757575>
                    </div>
                  ) : (
                    <>
                      {/* Section header */}
                      <div className="flex justify-between items-start px-[1.4rem] pt-[0.85rem] pb-[1.35rem]">
                        <Text_14_400_EEEEEE className="pt-[.55rem]">
                          Enter Credential Details
                        </Text_14_400_EEEEEE>
                      </div>
                      <div className="px-[1.4rem] flex justify-between items-center flex-wrap gap-[2rem] pb-[2rem]">
                        {[...visibleFields]
                          .sort((a, b) => a.order - b.order)
                          .map((field) => renderCredentialField(field))}
                      </div>
                    </>
                  )}
                </div>
              </div>

              {/* Footer — matches drawerFooter pattern */}
              <div className="drawerFooter z-[5000] min-[4.1875rem] flex flex-col justify-start">
                <div
                  style={{ justifyContent: "space-between" }}
                  className="h-[4rem] pt-[.1rem] flex items-center px-[2.7rem]"
                >
                  <SecondaryButton
                    onClick={closeDrawer}
                  >
                    Cancel
                  </SecondaryButton>
                  <PrimaryButton
                    onClick={handleSubmitCredentials}
                    loading={isSubmitting}
                    disabled={
                      isSubmitting ||
                      (credentialSchema.length > 0 && !isFormValid)
                    }
                    style={{
                      cursor:
                        isSubmitting ||
                        (credentialSchema.length > 0 && !isFormValid)
                          ? "not-allowed"
                          : "pointer",
                      transform: "none",
                    }}
                  >
                    {isSubmitting ? "Configuring..." : "Configure Connector"}
                  </PrimaryButton>
                </div>
              </div>
            </div>
          )}
        </div>
      </Drawer>


      {/* ---- Scoped styles ------------------------------------------------- */}
      <style jsx global>{`
        /* Let the global drawer body styles (border-radius, border) apply */
        .connectors-drawer .ant-drawer-content {
          background: transparent !important;
        }
        .connectors-drawer .ant-drawer-body {
          background: transparent !important;
        }

        /* Spin accent color */
        .ant-spin-dot-item {
          background-color: #965cde !important;
        }
      `}</style>
    </div>
  );
};

export default Connectors;
