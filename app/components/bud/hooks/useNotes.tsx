import { AppRequest } from "@/app/api/requests";
import ChatContext from "@/app/context/ChatContext";
import { useContext, useState } from "react";
import { tempApiBaseUrl } from "../environment";

export function useNotes() {
  const [loading, setLoading] = useState(false);
  const { chat } = useContext(ChatContext);
  const [notes, setNotes] = useState([] as any);
  const [currentPage, setCurrentPage] = useState(1);
  const [totalPages, setTotalPages] = useState(1);
  const [totalNotes, setTotalNotes] = useState(0);

  const createNote = async (note: string) => {
    try {
      const result = await AppRequest.Post(
        `${tempApiBaseUrl}/playground/chat-sessions/notes`,
        { note, chat_session_id: chat?.id }
      )
        .then((res) => {
          return res.data?.note;
        })
        ?.finally(() => {
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
      setLoading(true);
      const result = await AppRequest.Get(
        `${tempApiBaseUrl}/playground/chat-sessions/${chat?.id}/notes`,
        {
          params: { page: currentPage, limit: 10 },
        }
      ).then((res) => {
        console.log(res.data?.notes, notes);
        setTotalPages(res.data?.total_pages);
        setTotalNotes(res.data?.total_record);
        if (currentPage === 1) {
          setNotes(res.data?.notes);
        } else {
          setNotes([...notes, ...res.data?.notes]);
        }
        return res.data?.notes;
      });
      setLoading(false);
      console.log(`Notes retrieved: ${result}`);
      return result;
    } catch (error) {
      console.error(error);
    }
  };

  const updateNote = async (noteId: string, note: string) => {
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
      )
        .then((res) => {
          return res.data;
        })
        ?.finally(() => {
          getNotes();
        });

      console.log(`Note deleted: ${result}`);
      return result;
    } catch (error) {
      console.error(error);
    }
  };

  return { createNote, getNotes, updateNote, deleteNote, loading, notes, totalPages, totalNotes, setNotes, chat, currentPage, setCurrentPage};
}
