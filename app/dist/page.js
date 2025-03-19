"use client";
"use strict";
var __assign = (this && this.__assign) || function () {
    __assign = Object.assign || function(t) {
        for (var s, i = 1, n = arguments.length; i < n; i++) {
            s = arguments[i];
            for (var p in s) if (Object.prototype.hasOwnProperty.call(s, p))
                t[p] = s[p];
        }
        return t;
    };
    return __assign.apply(this, arguments);
};
var __awaiter = (this && this.__awaiter) || function (thisArg, _arguments, P, generator) {
    function adopt(value) { return value instanceof P ? value : new P(function (resolve) { resolve(value); }); }
    return new (P || (P = Promise))(function (resolve, reject) {
        function fulfilled(value) { try { step(generator.next(value)); } catch (e) { reject(e); } }
        function rejected(value) { try { step(generator["throw"](value)); } catch (e) { reject(e); } }
        function step(result) { result.done ? resolve(result.value) : adopt(result.value).then(fulfilled, rejected); }
        step((generator = generator.apply(thisArg, _arguments || [])).next());
    });
};
var __generator = (this && this.__generator) || function (thisArg, body) {
    var _ = { label: 0, sent: function() { if (t[0] & 1) throw t[1]; return t[1]; }, trys: [], ops: [] }, f, y, t, g;
    return g = { next: verb(0), "throw": verb(1), "return": verb(2) }, typeof Symbol === "function" && (g[Symbol.iterator] = function() { return this; }), g;
    function verb(n) { return function (v) { return step([n, v]); }; }
    function step(op) {
        if (f) throw new TypeError("Generator is already executing.");
        while (_) try {
            if (f = 1, y && (t = op[0] & 2 ? y["return"] : op[0] ? y["throw"] || ((t = y["return"]) && t.call(y), 0) : y.next) && !(t = t.call(y, op[1])).done) return t;
            if (y = 0, t) op = [op[0] & 2, t.value];
            switch (op[0]) {
                case 0: case 1: t = op; break;
                case 4: _.label++; return { value: op[1], done: false };
                case 5: _.label++; y = op[1]; op = [0]; continue;
                case 7: op = _.ops.pop(); _.trys.pop(); continue;
                default:
                    if (!(t = _.trys, t = t.length > 0 && t[t.length - 1]) && (op[0] === 6 || op[0] === 2)) { _ = 0; continue; }
                    if (op[0] === 3 && (!t || (op[1] > t[0] && op[1] < t[3]))) { _.label = op[1]; break; }
                    if (op[0] === 6 && _.label < t[1]) { _.label = t[1]; t = op; break; }
                    if (t && _.label < t[2]) { _.label = t[2]; _.ops.push(op); break; }
                    if (t[2]) _.ops.pop();
                    _.trys.pop(); continue;
            }
            op = body.call(thisArg, _);
        } catch (e) { op = [6, e]; y = 0; } finally { f = t = 0; }
        if (op[0] & 5) throw op[1]; return { value: op[0] ? op[1] : void 0, done: true };
    }
};
var __spreadArrays = (this && this.__spreadArrays) || function () {
    for (var s = 0, i = 0, il = arguments.length; i < il; i++) s += arguments[i].length;
    for (var r = Array(s), k = 0, i = 0; i < il; i++)
        for (var a = arguments[i], j = 0, jl = a.length; j < jl; j++, k++)
            r[k] = a[j];
    return r;
};
exports.__esModule = true;
var react_1 = require("react");
var Chat_1 = require("./components/Chat");
var RootContext_1 = require("./context/RootContext");
var useMessages_1 = require("./components/bud/hooks/useMessages");
var APIKey_1 = require("./components/APIKey");
var useEndPoint_1 = require("./components/bud/hooks/useEndPoint");
var appContext_1 = require("./context/appContext");
function Home() {
    var _this = this;
    var _a = react_1.useState(false), localMode = _a[0], setLocalMode = _a[1];
    var _b = react_1.useState(null), _accessToken = _b[0], _setAccessToken = _b[1];
    var _c = react_1.useState(null), _refreshToken = _c[0], _setRefreshToken = _c[1];
    var _d = react_1.useState(null), _apiKey = _d[0], _setApiKey = _d[1];
    var getSessions = useMessages_1.useMessages().getSessions;
    var getEndPoints = useEndPoint_1.useEndPoints().getEndPoints;
    var _e = react_1.useState([]), endpoints = _e[0], setEndpoints = _e[1];
    var token = _apiKey || _accessToken || "";
    var _f = react_1.useState([]), chats = _f[0], setChats = _f[1];
    var _g = react_1.useState([]), sessions = _g[0], setSessions = _g[1];
    // save to local storage
    react_1.useEffect(function () {
        if (!sessions || (sessions === null || sessions === void 0 ? void 0 : sessions.length) === 0)
            return;
        localStorage.setItem("sessions", JSON.stringify(sessions));
    }, [sessions]);
    // save to local storage
    react_1.useEffect(function () {
        console.log("syncing chats", chats);
        var validChats = chats.filter(function (chat) { return chat.id !== useMessages_1.NEW_SESSION; });
        if ((validChats === null || validChats === void 0 ? void 0 : validChats.length) === 0)
            return;
        localStorage.setItem("chats", JSON.stringify(validChats));
    }, [chats]);
    react_1.useEffect(function () {
        var init = function () {
            var _a, _b, _c, _d, _e, _f, _g, _h, _j, _k, _l;
            if (typeof window === "undefined")
                return null;
            var accessToken = (_c = (_b = (_a = window === null || window === void 0 ? void 0 : window.location.href) === null || _a === void 0 ? void 0 : _a.split("access_token=")) === null || _b === void 0 ? void 0 : _b[1]) === null || _c === void 0 ? void 0 : _c.split("&")[0];
            var refreshToken = (_g = (_f = (_e = (_d = window === null || window === void 0 ? void 0 : window.location.href) === null || _d === void 0 ? void 0 : _d.split("refresh_token=")) === null || _e === void 0 ? void 0 : _e[1]) === null || _f === void 0 ? void 0 : _f.split("&")) === null || _g === void 0 ? void 0 : _g[0];
            var _apiKey = (_l = (_k = (_j = (_h = window === null || window === void 0 ? void 0 : window.location.href) === null || _h === void 0 ? void 0 : _h.split("api_key=")) === null || _j === void 0 ? void 0 : _j[1]) === null || _k === void 0 ? void 0 : _k.split("&")) === null || _l === void 0 ? void 0 : _l[0];
            if (_apiKey) {
                _setApiKey(_apiKey);
            }
            if (accessToken && refreshToken) {
                _setAccessToken(accessToken);
                _setRefreshToken(refreshToken);
            }
        };
        init();
    }, []);
    var newChatPayload = {
        id: useMessages_1.NEW_SESSION,
        name: "New Chat",
        chat_setting: {
            temperature: 1,
            limit_response_length: true,
            min_p_sampling: 0.05,
            repeat_penalty: 0,
            sequence_length: 1000,
            stop_strings: [],
            structured_json_schema: {},
            system_prompt: "",
            top_k_sampling: 40,
            top_p_sampling: 1,
            context_overflow_policy: "auto",
            created_at: new Date().toISOString(),
            id: "new",
            modified_at: new Date().toISOString(),
            name: "new"
        },
        created_at: new Date().toISOString(),
        modified_at: new Date().toISOString(),
        total_tokens: 0
    };
    var closeChat = react_1.useCallback(function (chat) { return __awaiter(_this, void 0, void 0, function () {
        var updatedChats;
        return __generator(this, function (_a) {
            updatedChats = chats.filter(function (c) { return c.id !== chat.id; });
            if (updatedChats.length === 0) {
                updatedChats.push(newChatPayload);
            }
            setChats(updatedChats);
            return [2 /*return*/];
        });
    }); }, [chats, newChatPayload]);
    var createChat = react_1.useCallback(function (sessionId, replaceChatId) { return __awaiter(_this, void 0, void 0, function () {
        var updatedChats, session_1;
        return __generator(this, function (_a) {
            console.log("Creating chat");
            updatedChats = __spreadArrays(chats);
            if (!sessionId) {
                if (updatedChats.find(function (chat) { return chat.id === useMessages_1.NEW_SESSION; })) {
                    alert("You can only have one new chat at a time");
                    return [2 /*return*/];
                }
                updatedChats.push(newChatPayload);
            }
            else {
                session_1 = sessions.find(function (s) { return s.id === sessionId; });
                if (!session_1)
                    return [2 /*return*/];
                if (replaceChatId) {
                    updatedChats = updatedChats.map(function (chat) {
                        if (chat.id === replaceChatId) {
                            return session_1;
                        }
                        return chat;
                    });
                }
                else {
                    updatedChats.push(session_1);
                }
            }
            setChats(updatedChats);
            return [2 /*return*/];
        });
    }); }, [chats, endpoints, sessions, newChatPayload]);
    react_1.useEffect(function () {
        var init = function () { return __awaiter(_this, void 0, void 0, function () {
            var localMode, existing, data, sessionsResult, endpointResult;
            return __generator(this, function (_a) {
                switch (_a.label) {
                    case 0:
                        if (!token)
                            return [2 /*return*/];
                        localStorage.setItem("token", token);
                        localMode = false;
                        if (token === null || token === void 0 ? void 0 : token.startsWith("budserve_")) {
                            setLocalMode(true);
                        }
                        if (!localMode) return [3 /*break*/, 1];
                        existing = localStorage.getItem("sessions");
                        if (existing) {
                            console.log("Getting sessions from local storage");
                            data = JSON.parse(existing);
                            setSessions(data);
                        }
                        return [3 /*break*/, 3];
                    case 1:
                        console.log("Getting sessions");
                        return [4 /*yield*/, getSessions()];
                    case 2:
                        sessionsResult = _a.sent();
                        setSessions(sessionsResult);
                        _a.label = 3;
                    case 3: return [4 /*yield*/, getEndPoints({ page: 1, limit: 25 })];
                    case 4:
                        endpointResult = _a.sent();
                        setTimeout(function () {
                            var existing = localStorage.getItem("chats");
                            if (existing) {
                                var data = JSON.parse(existing);
                                setChats(data);
                            }
                            else if (chats.length === 0 && endpointResult) {
                                createChat();
                            }
                        }, 100);
                        return [2 /*return*/];
                }
            });
        }); };
        init();
    }, [token]);
    var handleDeploymentSelect = react_1.useCallback(function (chat, endpoint) {
        if (!chat)
            return;
        var updatedChats = __spreadArrays(chats);
        updatedChats = updatedChats.map(function (_chat) {
            if (_chat.id === chat.id) {
                _chat.selectedDeployment = endpoint;
            }
            return _chat;
        });
        setChats(updatedChats);
    }, [chats]);
    var handleSettingsChange = function (chat, prop, value) {
        var updatedChats = __spreadArrays(chats);
        updatedChats = updatedChats.map(function (item) {
            var _a;
            if (item.id === (chat === null || chat === void 0 ? void 0 : chat.id)) {
                return __assign(__assign({}, item), { chat_setting: __assign(__assign({}, item.chat_setting), (_a = {}, _a[prop] = value, _a)) });
            }
            return item;
        });
        setChats(updatedChats);
    };
    return (React.createElement("main", { className: "flex flex-col gap-8 row-start-2 items-center w-full h-[100vh]" },
        React.createElement(RootContext_1["default"].Provider, { value: {
                chats: chats,
                setChats: setChats,
                createChat: createChat,
                closeChat: closeChat,
                handleDeploymentSelect: handleDeploymentSelect,
                handleSettingsChange: handleSettingsChange,
                token: token,
                sessions: sessions,
                setSessions: setSessions,
                endpoints: endpoints,
                setEndpoints: setEndpoints,
                localMode: localMode
            } },
            React.createElement(appContext_1.AuthNavigationProvider, null,
                React.createElement(appContext_1.LoaderProvider, null, (chats === null || chats === void 0 ? void 0 : chats.length) === 0 ? React.createElement(APIKey_1["default"], null) : React.createElement(Chat_1["default"], null))))));
}
exports["default"] = Home;
