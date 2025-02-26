"use client";

import { useChat } from "@ai-sdk/react";
import NavBar from "./components/bud/components/navigation/NavBar";
import { Image } from "antd";
import Editor from "./components/bud/components/input/Editor";
import Messages from "./components/bud/chat/Messages";
import { Layout } from "antd";
import HistoryList from "./components/bud/chat/HistoryList";
import SettingsList from "./components/bud/chat/SettingsList";
import { useEffect, useState } from "react";
import NormalEditor from "./components/bud/components/input/NormalEditor";
import MessageLoading from "./components/bud/chat/MessageLoading";
import Chat from "./components/bud/chat/Chat";
import ChatContext from "./context/ChatContext";
import { apiKey } from "./components/bud/environment";
import { useEndPoints } from "./components/bud/hooks/useEndPoint";

const { Header, Footer, Sider, Content } = Layout;

export default function Page() {
  return <Chat />;
}
