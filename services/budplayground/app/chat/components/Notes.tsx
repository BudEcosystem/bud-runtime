"use client";

import { v4 as uuidv4 } from 'uuid';
import CustomPopover from "@/app/components/bud/components/customPopover";
import { useChatStore } from "@/app/store/chat";
import { Note } from "@/app/types/chat";
import { Button, Image, Input } from "antd";
import { useState } from "react";


function NoteItem({note}: {note: Note}) {
    const { updateNote, deleteNote } = useChatStore();
    const [noteValue, setNoteValue] = useState(note.note);

    const handleChange = (value: string) => {
        setNoteValue(value);
        updateNote({
            ...note,
            note: value
        });
    }
    return (
        <div
      className={`flex items-start rounded-[6px] relative !bg-[transparent]  w-full my-[1rem]`}
    >
      <div className="w-full">
        <div className="absolute !bg-[#101010] px-[.25rem] rounded -top-2 left-[.5rem] tracking-[.035rem] z-10 flex items-center gap-1 text-[.75rem] text-[#EEEEEE] font-[300] text-nowrap">
          Note
          <CustomPopover
            title="Conversation Notes"
            classNames="flex items-center"
          >
            <Image
              preview={false}
              src="/icons/info.svg"
              alt="info"
              style={{ width: ".75rem", height: ".75rem" }}
            />
          </CustomPopover>
        </div>
        <div className="absolute !bg-[#101010] px-[.5rem] rounded -top-1 right-[.5rem] tracking-[.035rem] z-10 flex items-center gap-1 text-[.75rem] text-[#EEEEEE] font-[300] text-nowrap cursor-pointer opacity-80 hover:opacity-50" onClick={() => deleteNote(note.id)}>
            <Image
              preview={false}
              src="/icons/delete.png"
              alt="delete"
              style={{ width: ".75rem", height: ".75rem" }}
            />
        </div>
        <Input.TextArea
          defaultValue={note.note}
          placeholder="Type your notes here"
          style={{
            backgroundColor: "transparent",
            color: "#EEEEEE",
            border: "0.5px solid #757575",
          }}
          value={noteValue}
          onChange={(e) => handleChange(e.target.value)}
          size="large"
          className="drawerInp py-[.65rem] bg-transparent text-[#EEEEEE] font-[300] border-[0.5px] border-[#757575] rounded-[6px] hover:border-[#EEEEEE] focus:border-[#EEEEEE] active:border-[#EEEEEE] text-[.75rem] shadow-none w-full indent-[.4rem]"
        />
      </div>
    </div>
    )
}

export default function Notes({chatId}: {chatId: string}) {
    const { getNotes, addNote } = useChatStore();

    const notes = getNotes(chatId);
    const handleScroll = () => {
        console.log("scrolling");
    }

    const createNote = () => {
        addNote({
            id: uuidv4(),
            note: "",
            created_at: new Date().toISOString(),
            modified_at: new Date().toISOString(),
            chat_session_id: chatId
        });
    }

    return (
        <div onScroll={handleScroll} className="px-[.5rem]">
          {notes?.map((note: any) => (
            <NoteItem key={note.id || `note-${notes.indexOf(note)}`} note={note} />
          ))}
          <Button
            onClick={() => {
              createNote();
            }}
            icon={<Image src="icons/plus.svg" alt="Add note" preview={false} />}
            className="flex items-center justify-center w-full h-[2rem] bg-[#D1B854] text-[#101010] text-[.75rem] font-[400] rounded-[6px]"
            type="primary"
          >
            {notes?.length > 0 ? "Add Note" : "Add another note"}
          </Button>
        </div>
      );
}
