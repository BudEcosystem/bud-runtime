"use client";

import { useChat } from "@ai-sdk/react";
import NavBar from "./components/bud/components/navigation/NavBar";
import { Image } from "antd";
import Editor from "./components/bud/components/input/Editor";
import Messages from "./components/bud/chat/Messages";
import { Layout } from "antd";
import HistoryList from "./components/bud/chat/HistoryList";
import SettingsList from "./components/bud/chat/SettingsList";
import { useState } from "react";
import NormalEditor from "./components/bud/components/input/NormalEditor";
import MessageLoading from "./components/bud/chat/MessageLoading";
import Chat from "./components/bud/chat/Chat";

const { Header, Footer, Sider, Content } = Layout;

export default function Page() {
 
  return (
    <Chat />
  );
}
