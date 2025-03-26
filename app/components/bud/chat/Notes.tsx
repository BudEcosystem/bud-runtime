import React, { useContext, useEffect } from "react";
import LabelTextArea from "../components/input/LabelTextArea";
import { useNotes } from "../hooks/useNotes";
import ChatContext from "@/app/context/ChatContext";
import { Button, Image } from "antd";

function Notes() {
  const {
    getNotes,
    createNote,
    deleteNote,
    currentPage,
    setCurrentPage,
    updateNote,
    chat,
    notes,
    totalNotes,
    totalPages,
    setNotes,
  } = useNotes();
  const chatNotes = `chat-${chat?.id}-notes`;

  useEffect(() => {
    getNotes();
  }, [currentPage]);

  const handleScroll = () => {
    console.log("scrolling");
    // is at the bottom
    const content = document.getElementById(chatNotes);
    if (content) {
      const bottom = content?.scrollTop > notes.length * 30;
      console.log(bottom, notes.length, totalNotes, currentPage, totalPages);
      if (bottom && notes.length < totalNotes && currentPage < totalPages) {
        setCurrentPage(currentPage + 1);
      }
    }
  };

  return (
    <div
      id={chatNotes}
      onScroll={handleScroll}
    >
      {notes?.map((note) => (
        <div className="flex flex-col w-full gap-[.5rem] py-[.375rem] max-h-[20rem] overflow-y-auto">
          <LabelTextArea
            title="Notes"
            placeholder="Type your notes here"
            description="Conversation Notes"
            value={note.note}
            defaultValue={note.note}
            onChange={(value) => {
              setNotes(
                notes.map((n) => (n.id === note.id ? { ...n, note: value } : n))
              );
            }}
            onBlur={() => {
              updateNote(note.id, note.note);
            }}
          />
        </div>
      ))}
      <Button
        onClick={() => {
          createNote("New Note");
        }}
        icon={<Image src="icons/plus.svg" preview={false} />}
        className="flex items-center justify-center w-full h-[2rem] bg-[#D1B854] text-[#101010] text-[.75rem] font-[400] rounded-[6px]"
        type="primary"
      >
        {notes?.length > 0 ? "Add Note" : "Add another note"}
      </Button>
    </div>
  );
}

export default Notes;
