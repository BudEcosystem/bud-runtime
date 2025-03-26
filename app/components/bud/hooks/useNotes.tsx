import { AppRequest } from "@/app/api/requests";
import ChatContext from "@/app/context/ChatContext";
import { useContext } from "react";
import { tempApiBaseUrl } from "../environment";

export function useNotes() {
  const { chat, setNotes, notes } = useContext(ChatContext);

  const createNote = async (note: string) => {
    try {
      const result = await AppRequest.Post(
        `${tempApiBaseUrl}/playground/chat-sessions/notes`,
        { note, chat_session_id: chat?.id }
      ).then((res) => {
        return res.data?.note;
      })?.finally(() => {
        getNotes();
      });

      console.log(`Note created: ${result.id}`);
      return result;
    } catch (error) {
      console.error(error);
    }
  };

  const getNotes = async () => {
    try {
      const result = await AppRequest.Get(
        `${tempApiBaseUrl}/playground/chat-sessions/${chat?.id}/notes`
      ).then((res) => {
        console.log(res.data?.notes, notes);
        setNotes(res.data?.notes);
        return res.data?.notes;
      });

      console.log(`Notes retrieved: ${result}`);
      return result;
    } catch (error) {
      console.error(error);
    }
  };

  const updateNote = async (noteId: string, note: string, ) => {
    try {
      const result = await AppRequest.Patch(
        `${tempApiBaseUrl}/playground/chat-sessions/notes/${noteId}`,
        { note }
      ).then((res) => {
        return res.data?.note;
      });
      console.log(`Note updated: ${result.id}`);
      return result;
    } catch (error) {
      console.error(error);
    }
  };

  const deleteNote = async (noteId: string) => {
    try {
      const result = await AppRequest.Delete(
        `${tempApiBaseUrl}/playground/chat-sessions/notes/${noteId}`
      ).then((res) => {
        return res.data;
      })?.finally(() => {
        getNotes();
      });

      console.log(`Note deleted: ${result}`);
      return result;
    } catch (error) {
      console.error(error);
    }
  };

  return { createNote, getNotes, updateNote, deleteNote };
}
