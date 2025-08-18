import { BudWraperBox } from "@/components/ui/bud/card/wraperBox";
import { BudDrawerLayout } from "@/components/ui/bud/dataEntry/BudDrawerLayout";
import { BudForm } from "@/components/ui/bud/dataEntry/BudForm";
import DrawerTitleCard from "@/components/ui/bud/card/DrawerTitleCard";
import { Input, Checkbox, Tag, Button, Select, ConfigProvider, Modal, Popover } from "antd";
import { PlusOutlined, DeleteOutlined, EyeOutlined, CloseOutlined } from "@ant-design/icons";
import React, { useState } from "react";
import { useDrawer } from "src/hooks/useDrawer";
import {
  Text_10_400_757575,
  Text_12_400_757575,
  Text_12_400_B3B3B3,
  Text_12_400_EEEEEE,
  Text_12_300_EEEEEE,
  Text_14_400_EEEEEE,
  Text_14_600_FFFFFF,
} from "@/components/ui/text";

interface GuardRailRule {
  id: string;
  type: 'regex' | 'semantic' | 'word';
  pattern?: string;
  words?: string[];
  preview?: string[];
  options?: {[key: string]: boolean};
}

const WORD_SUGGESTIONS = ["Hello", "Hi", "Howdy", "Greetings", "Welcome", "Hey", "Good morning", "Good afternoon", "Good evening"];

export default function AddCustomGuardRail() {
  const { openDrawerWithStep } = useDrawer();
  const [rules, setRules] = useState<GuardRailRule[]>([
    { id: "1", type: "regex", pattern: "" },
    { id: "2", type: "word", words: ["Hi"] },
  ]);
  const [budExpression, setBudExpression] = useState("");
  const [wordModalVisible, setWordModalVisible] = useState(false);
  const [ruleConfigModalVisible, setRuleConfigModalVisible] = useState(false);
  const [activeRuleId, setActiveRuleId] = useState<string>("");
  const [searchWord, setSearchWord] = useState("");
  const [tempSelectedWords, setTempSelectedWords] = useState<string[]>([]);
  const [ruleOptions, setRuleOptions] = useState<{[key: string]: any}>({});

  const handleBack = () => {
    openDrawerWithStep("select-probe-type");
  };

  const handleSave = () => {
    // Save configuration and move to guard rail details
    openDrawerWithStep("guardrail-details");
  };

  const addRule = () => {
    const newRule: GuardRailRule = {
      id: Date.now().toString(),
      type: "regex",
      pattern: "",
    };
    setRules([...rules, newRule]);
  };

  const removeRule = (id: string) => {
    if (rules.length > 1) {
      setRules(rules.filter((r) => r.id !== id));
    }
  };

  const updateRule = (id: string, updates: Partial<GuardRailRule>) => {
    setRules(
      rules.map((r) => (r.id === id ? { ...r, ...updates } : r))
    );
  };

  const openWordSelector = (ruleId: string) => {
    const rule = rules.find(r => r.id === ruleId);
    setActiveRuleId(ruleId);
    setTempSelectedWords(rule?.words || []);
    setSearchWord("");
    setWordModalVisible(true);
  };

  const closeWordSelector = () => {
    setWordModalVisible(false);
    setActiveRuleId("");
    setTempSelectedWords([]);
    setSearchWord("");
  };

  const applyWordSelection = () => {
    updateRule(activeRuleId, { words: tempSelectedWords });
    closeWordSelector();
  };

  const addWordToSelection = (word: string) => {
    if (!tempSelectedWords.includes(word)) {
      setTempSelectedWords([...tempSelectedWords, word]);
    }
  };

  const removeWordFromSelection = (word: string) => {
    setTempSelectedWords(tempSelectedWords.filter(w => w !== word));
  };

  const openRuleConfig = (ruleId: string) => {
    setActiveRuleId(ruleId);
    const rule = rules.find(r => r.id === ruleId);
    if (rule) {
      setRuleOptions(rule.options || {});
    }
    setRuleConfigModalVisible(true);
  };

  const closeRuleConfig = () => {
    setRuleConfigModalVisible(false);
    setActiveRuleId("");
    setRuleOptions({});
  };

  const applyRuleConfig = () => {
    updateRule(activeRuleId, { options: ruleOptions });
    closeRuleConfig();
  };

  const getRuleConfigOptions = (ruleType: string) => {
    switch (ruleType) {
      case 'regex':
        return [
          { key: 'allowAlphanumeric', label: 'Allow alphanumeric characters' },
          { key: 'filterAlphanumeric', label: 'Filter alphanumeric characters' },
          { key: 'allowNumbers', label: 'Allow numbers only' },
          { key: 'filterNumbers', label: 'Filter numbers' },
          { key: 'allowLetters', label: 'Allow letters only' },
          { key: 'filterLetters', label: 'Filter letters' },
          { key: 'caseSensitive', label: 'Case sensitive matching' },
          { key: 'multiline', label: 'Multiline matching' },
        ];
      case 'semantic':
        return [
          { key: 'strictMatching', label: 'Strict semantic matching' },
          { key: 'contextAware', label: 'Context-aware detection' },
          { key: 'synonymMatching', label: 'Include synonyms' },
          { key: 'relatedConcepts', label: 'Match related concepts' },
          { key: 'sentimentAnalysis', label: 'Consider sentiment' },
        ];
      case 'word':
        return [
          { key: 'exactMatch', label: 'Exact word matching' },
          { key: 'partialMatch', label: 'Partial word matching' },
          { key: 'caseSensitive', label: 'Case sensitive' },
          { key: 'wholeWord', label: 'Whole word only' },
          { key: 'stemming', label: 'Include word stems' },
          { key: 'plurals', label: 'Include plurals' },
        ];
      default:
        return [];
    }
  };

  const removeWordFromRule = (ruleId: string, word: string) => {
    const rule = rules.find(r => r.id === ruleId);
    if (rule?.words) {
      updateRule(ruleId, {
        words: rule.words.filter(w => w !== word)
      });
    }
  };

  const getFilteredSuggestions = () => {
    if (!searchWord) return WORD_SUGGESTIONS.slice(0, 5);
    return WORD_SUGGESTIONS
      .filter(word => word.toLowerCase().startsWith(searchWord.toLowerCase()))
      .slice(0, 5);
  };

  const generateRuleEffects = (rule: GuardRailRule): string[] => {
    const effects: string[] = [];

    if (rule.type === 'regex' && rule.pattern) {
      // Analyze regex pattern to determine effects
      if (rule.pattern.includes('[0-9]') || rule.pattern.includes('\\d')) {
        effects.push('• Filters numbers');
      }
      if (rule.pattern.includes('[a-zA-Z]') || rule.pattern.includes('\\w')) {
        effects.push('• Filters alphabets');
      }
      if (rule.pattern.includes('[^') || rule.pattern.includes('!')) {
        effects.push('• Excludes specific characters');
      }
      if (rule.pattern.includes('+') || rule.pattern.includes('*')) {
        effects.push('• Matches multiple occurrences');
      }
      if (rule.pattern.includes('^')) {
        effects.push('• Matches start of text');
      }
      if (rule.pattern.includes('$')) {
        effects.push('• Matches end of text');
      }
      if (effects.length === 0) {
        effects.push(`• Matches pattern: ${rule.pattern}`);
      }
    } else if (rule.type === 'semantic' && rule.pattern) {
      effects.push(`• Semantic similarity matching`);
      effects.push(`• Finds related meanings to: "${rule.pattern}"`);
      effects.push(`• Context-aware detection`);
    } else if (rule.type === 'word' && rule.words?.length) {
      effects.push(`• Blocks exact word matches`);
      if (rule.words.length > 0) {
        effects.push(`• Filters: ${rule.words.slice(0, 3).join(', ')}${rule.words.length > 3 ? '...' : ''}`);
      }
      effects.push(`• Case-sensitive matching`);
    } else {
      effects.push('• No effects - configure the rule');
    }

    return effects;
  };

  return (
    <BudForm
      data={{}}
      onBack={handleBack}
      onNext={handleSave}
      backText="Back"
      nextText="Save"
    >
      <BudWraperBox >
        <BudDrawerLayout>
          <DrawerTitleCard
            title="Add Custom GuardRail"
            description="Define custom guardrail rules using RegEx, Semantic, or Text matching"
            classNames="pt-[.8rem]"
            descriptionClass="pt-[.3rem]"
          />

          <div className="px-[1.35rem] pb-[1.35rem]">
            {/* Rules Configuration */}
            <div className="space-y-[1rem] mb-[1.5rem]">
              {rules.map((rule) => (
                <div key={rule.id} className="flex gap-[0.75rem] items-center">
                  {/* Type Selector */}
                  <div className="w-[140px] custom-select-two">
                    <ConfigProvider
                      theme={{
                        token: {
                          colorTextPlaceholder: "#808080",
                          boxShadowSecondary: "none",
                          colorBorder: "#757575",
                        },
                      }}
                    >
                      <Select
                        value={rule.type}
                        onChange={(value) => {
                          updateRule(rule.id, {
                            type: value,
                            pattern: value !== 'word' ? '' : undefined,
                            words: value === 'word' ? [] : undefined
                          });
                        }}
                        style={{
                          backgroundColor: "transparent",
                          color: "#EEEEEE",
                          border: "0.5px solid #757575",
                        }}
                        className="w-full !bg-transparent !border-[#757575] hover:!border-[#EEEEEE]"
                        variant="outlined"
                        options={[
                          { label: "RegEx", value: "regex" },
                          { label: "Semantic", value: "semantic" },
                          { label: "Text", value: "word" },
                        ]}
                      />
                    </ConfigProvider>
                  </div>

                  {/* Pattern/Words Field */}
                  <div className="flex-1">
                    {rule.type === 'word' ? (
                      <div
                        className="h-[32px] px-[11px] py-[4px] border border-[#757575] rounded-[6px] bg-transparent hover:border-[#EEEEEE] cursor-pointer flex gap-[4px] items-center overflow-hidden"
                        onClick={() => openWordSelector(rule.id)}
                      >
                        {rule.words && rule.words.length > 0 ? (
                          <div className="flex gap-[4px] items-center overflow-hidden flex-nowrap">
                            {rule.words.slice(0, 2).map((word) => (
                              <Tag
                                key={word}
                                closable
                                onClose={(e) => {
                                  e.preventDefault();
                                  removeWordFromRule(rule.id, word);
                                }}
                                className="bg-[#965CDE20] border-[#965CDE] text-[#EEEEEE] m-0 flex-shrink-0"
                              >
                                {word}
                              </Tag>
                            ))}
                            {rule.words.length > 2 && (
                              <Text_12_400_757575 className="flex-shrink-0">
                                +{rule.words.length - 2} more...
                              </Text_12_400_757575>
                            )}
                          </div>
                        ) : (
                          <Text_12_400_757575>Select words...</Text_12_400_757575>
                        )}
                      </div>
                    ) : (
                      <Input
                        placeholder={rule.type === 'regex' ? "Pattern" : "Semantic pattern"}
                        value={rule.pattern}
                        onChange={(e) => updateRule(rule.id, { pattern: e.target.value })}
                        className="bg-transparent text-[#EEEEEE] border-[#757575] hover:border-[#EEEEEE]"
                        style={{ backgroundColor: "transparent" }}
                      />
                    )}
                  </div>

                  {/* Configure Button */}
                  <Button
                    icon={<EyeOutlined />}
                    onClick={() => openRuleConfig(rule.id)}
                    className="!bg-transparent border-[#757575] text-[#757575] hover:!bg-[#FFFFFF08] hover:!border-[#EEEEEE] hover:!text-[#EEEEEE]"
                    style={{ backgroundColor: "transparent" }}
                    title="Configure rule options"
                  />

                  {/* Delete Button */}
                  {rules.length > 1 && (
                    <Button
                      icon={<DeleteOutlined />}
                      onClick={() => removeRule(rule.id)}
                      className="!bg-transparent hover:!bg-[#FF000010]"
                      style={{ backgroundColor: "transparent", color: "#ec7575", borderColor: "#ec7575" }}
                      danger
                    />
                  )}
                </div>
              ))}

              {/* Add New Field Button */}
              <Button
                icon={<PlusOutlined />}
                onClick={addRule}
                className="!bg-transparent text-[#965CDE] border-[#965CDE] hover:!bg-[#965CDE10]"
                style={{ backgroundColor: "transparent" }}
                type="dashed"
              >
                New Field
              </Button>
            </div>

            {/* Caution Message */}
            <div className="mb-[1rem] p-[0.75rem] bg-[#d1b85410] border border-[#d1b854] rounded-[6px]">
              <Text_10_400_757575 className="text-[#d1b854]">
                ⚠️ Caution: We currently only support OR based matching. For the input fields we select if any of them match.
              </Text_10_400_757575>
            </div>

            {/* Bud Expression */}
            <div>
              <Text_14_400_EEEEEE className="mb-[0.5rem]">
                Bud Expression (If, any)
              </Text_14_400_EEEEEE>
              <Input.TextArea
                value={budExpression}
                onChange={(e) => setBudExpression(e.target.value)}
                placeholder="Enter optional Bud expression"
                rows={3}
                className="bg-transparent text-[#EEEEEE] border-[#757575] font-mono"
                style={{ backgroundColor: "transparent", minHeight: "120px" }}
              />
            </div>
          </div>
        </BudDrawerLayout>
      </BudWraperBox>

      {/* Word Selection Modal */}
      <ConfigProvider
        theme={{
          token: {
            colorBgElevated: "#101010",
            colorBorder: "#1F1F1F",
            colorText: "#EEEEEE",
            colorTextDescription: "#757575",
            colorBgContainer: "#101010",
          },
        }}
      >
        <Modal
          title={
            <div className="flex items-center justify-between">
              <Text_14_600_FFFFFF>Select Words</Text_14_600_FFFFFF>
              <Button
                icon={<CloseOutlined />}
                onClick={closeWordSelector}
                type="text"
                className="!text-[#757575] hover:!text-[#EEEEEE] hover:!bg-[#FFFFFF10]"
              />
            </div>
          }
          closable={false}
          open={wordModalVisible}
          onCancel={closeWordSelector}
          footer={[
            <Button
              key="cancel"
              onClick={closeWordSelector}
              className="!bg-transparent !text-[#EEEEEE] !border-[#757575] hover:!border-[#EEEEEE]"
            >
              Cancel
            </Button>,
            <Button
              key="add"
              type="primary"
              onClick={applyWordSelection}
              className="!bg-[#965CDE] !border-[#965CDE] hover:!bg-[#8A4FD3]"
            >
              Add
            </Button>,
          ]}
          className="custom-modal"
          styles={{
            content: {
              boxShadow: '0px 0px 5px 1px #7575754a',
              borderRadius: '10px'
            }
          }}
        >
        {/* Search Input */}
        <div className="mb-[1rem]">
          <Input
            placeholder="Type to search words..."
            value={searchWord}
            onChange={(e) => setSearchWord(e.target.value)}
            className="bg-transparent text-[#EEEEEE] border-[#757575]"
            style={{ backgroundColor: "transparent" }}
          />
        </div>

        {/* Selected Words */}
        {tempSelectedWords.length > 0 && (
          <div className="mb-[1rem] p-[0.75rem] bg-[#FFFFFF08] rounded-[6px] border border-[#1F1F1F]">
            <Text_12_400_757575 className="mb-[0.5rem]">Selected words:</Text_12_400_757575>
            <div className="flex flex-wrap gap-[0.5rem]">
              {tempSelectedWords.map((word) => (
                <Tag
                  key={word}
                  closable
                  onClose={() => removeWordFromSelection(word)}
                  className="bg-[#965CDE20] border-[#965CDE] text-[#EEEEEE]"
                >
                  {word}
                </Tag>
              ))}
            </div>
          </div>
        )}

        {/* Suggestions List */}
        <div className="space-y-[0.5rem]">
          <Text_12_400_757575 className="mb-[0.5rem]">Click to add:</Text_12_400_757575>
          {getFilteredSuggestions().map((word) => {
            const isSelected = tempSelectedWords.includes(word);
            return (
              <div
                key={word}
                className={`p-[0.5rem] border rounded-[6px] cursor-pointer transition-all ${
                  isSelected
                    ? "border-[#965CDE50] bg-[#965CDE10] opacity-50 cursor-not-allowed"
                    : "border-[#757575] hover:border-[#965CDE] hover:bg-[#965CDE10]"
                }`}
                onClick={() => !isSelected && addWordToSelection(word)}
              >
                <div className="flex items-center justify-between">
                  <Text_12_400_EEEEEE className={isSelected ? "opacity-50" : ""}>
                    {word}
                  </Text_12_400_EEEEEE>
                  {isSelected && (
                    <Text_10_400_757575>Already added</Text_10_400_757575>
                  )}
                </div>
              </div>
            );
          })}
          {getFilteredSuggestions().length === 0 && (
            <Text_12_400_757575>No suggestions found</Text_12_400_757575>
          )}
        </div>
        </Modal>
      </ConfigProvider>

      {/* Rule Configuration Modal */}
      <ConfigProvider
        theme={{
          token: {
            colorBgElevated: "#101010",
            colorBorder: "#1F1F1F",
            colorText: "#EEEEEE",
            colorTextDescription: "#757575",
            colorBgContainer: "#101010",
          },
        }}
      >
        <Modal
          title={
            <div className="flex items-center justify-between">
              <Text_14_600_FFFFFF>Configure Rule Options</Text_14_600_FFFFFF>
              <Button
                icon={<CloseOutlined />}
                onClick={closeRuleConfig}
                type="text"
                className="!text-[#757575] hover:!text-[#EEEEEE] hover:!bg-[#FFFFFF10]"
              />
            </div>
          }
          closable={false}
          open={ruleConfigModalVisible}
          onCancel={closeRuleConfig}
          footer={[
            <Button
              key="cancel"
              onClick={closeRuleConfig}
              className="!bg-transparent !text-[#EEEEEE] !border-[#757575] hover:!border-[#EEEEEE]"
            >
              Cancel
            </Button>,
            <Button
              key="apply"
              type="primary"
              onClick={applyRuleConfig}
              className="!bg-[#965CDE] !border-[#965CDE] hover:!bg-[#8A4FD3]"
            >
              Apply
            </Button>,
          ]}
          className="custom-modal"
          width={500}
          styles={{
            content: {
              boxShadow: '0px 0px 5px 1px #7575754a',
              borderRadius: '10px'
            }
          }}
        >
          {activeRuleId && (
            <div>
              {/* Rule Type Info */}
              <div className="mb-[1rem] p-[0.75rem] bg-[#FFFFFF08] rounded-[6px] border border-[#1F1F1F]">
                <div className="flex items-center gap-[0.5rem]">
                  <Text_12_400_757575>Rule Type:</Text_12_400_757575>
                  <Text_14_400_EEEEEE className="capitalize">
                    {rules.find(r => r.id === activeRuleId)?.type}
                  </Text_14_400_EEEEEE>
                </div>
              </div>

              {/* Configuration Options */}
              <div>
                <Text_14_400_EEEEEE className="mb-[0.75rem]">
                  Configuration Options:
                </Text_14_400_EEEEEE>
                <div className="space-y-[0.5rem] max-h-[300px] overflow-y-auto">
                  {getRuleConfigOptions(rules.find(r => r.id === activeRuleId)?.type || '').map((option) => (
                    <div key={option.key} className="flex items-start gap-[0.5rem]">
                      <Checkbox
                        checked={ruleOptions[option.key] || false}
                        onChange={(e) => {
                          setRuleOptions({
                            ...ruleOptions,
                            [option.key]: e.target.checked
                          });
                        }}
                        className="AntCheckbox mt-[2px]"
                      />
                      <div className="flex-1">
                        <Text_12_400_EEEEEE>{option.label}</Text_12_400_EEEEEE>
                      </div>
                    </div>
                  ))}
                </div>
              </div>

              {/* Preview Section */}
              <div className="mt-[1.5rem] p-[0.75rem] bg-[#FFFFFF08] rounded-[6px] border border-[#1F1F1F]">
                <Text_12_400_757575 className="mb-[0.5rem]">Selected Options:</Text_12_400_757575>
                <div className="space-y-[0.25rem]">
                  {Object.entries(ruleOptions).filter(([_, value]) => value).length > 0 ? (
                    Object.entries(ruleOptions)
                      .filter(([_, value]) => value)
                      .map(([key, _]) => {
                        const option = getRuleConfigOptions(rules.find(r => r.id === activeRuleId)?.type || '')
                          .find(opt => opt.key === key);
                        return (
                          <Text_10_400_757575 key={key} className="text-[#965CDE]">
                            • {option?.label}
                          </Text_10_400_757575>
                        );
                      })
                  ) : (
                    <Text_10_400_757575>No options selected</Text_10_400_757575>
                  )}
                </div>
              </div>
            </div>
          )}
        </Modal>
      </ConfigProvider>
    </BudForm>
  );
}
