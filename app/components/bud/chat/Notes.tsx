import React, { useContext, useEffect } from "react";
import LabelTextArea from "../components/input/LabelTextArea";
import { useNotes } from "../hooks/useNotes";
import ChatContext from "@/app/context/ChatContext";
import { Button, Image } from "antd";
import RootContext from "@/app/context/RootContext";

function Notes() {
  // const { localMode } = useContext(RootContext);
  const localMode = true;
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
    localStorage.setItem(chatNotes, JSON.stringify(notes));
  }, [notes]);

  useEffect(() => {
    if (localMode) {
      const localNotes = localStorage.getItem(chatNotes);

      console.log("localNotes", localNotes);
      if (localNotes) {
        try {
          setNotes(JSON.parse(localNotes));
        } catch (error) {
          console.error("Error parsing localNotes JSON", error);
        }
      }
    } else {
      getNotes();
    }
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
    <div id={chatNotes} onScroll={handleScroll} className="px-[.5rem]">
      {notes?.map((note: any) => (
        <div className="flex flex-col w-full gap-[.5rem] py-[.375rem] max-h-[20rem] overflow-y-auto">
          <LabelTextArea
            title="Notes"
            placeholder="Type your notes here"
            description="Conversation Notes"
            value={note.note}
            defaultValue={note.note}
            onChange={(value) => {
              setNotes(
                notes.map((n: any) => (n.id === note.id ? { ...n, note: value } : n))
              );
            }}
            onBlur={() => {
              if (note.note === "") {
                deleteNote(note.id);
              } else {
                updateNote(note.id, note.note);
              }
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
