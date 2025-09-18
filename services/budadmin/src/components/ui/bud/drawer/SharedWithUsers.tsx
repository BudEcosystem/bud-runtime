import { Avatar, Image, Tooltip } from "antd";
import React from "react";
import CustomPopover from "src/flows/components/customPopover";
import { ProjectMember } from "src/hooks/useProjects";

export default function SharedWithUsers({ users_count, users_colours }) {
  // Generate avatars with corresponding colors or fallback to transparent
  const usersArray = Array(users_count)
    .fill(null)
    .map((_, index) => (
      <Avatar
        key={index}
        className="w-[1.8rem] h-[1.8rem]"
        src={
          <Image
            preview={false}
            src="/images/drawer/memoji.png"
            alt="memoji"
            className="w-full h-full rounded-full"
            style={{
              padding: "1px",
            }}
          />
        }
        style={{
          backgroundColor: users_colours?.[index] || "transparent", // Set transparent if no color is provided
        }}
      />
    ));

  return (
    <Avatar.Group
      className="flex items-center justify-center"
      max={{
        count: 2,
        style: {
          color: "#EEEEEE",
          backgroundColor: "#29292B",
        },
      }}
      shape="circle"
    >
      {usersArray}
    </Avatar.Group>
  );
}

export function SharedWithProjectUsers({ users }: { users: ProjectMember[] }) {
  const usersArray = users.map((user, index) => (
    <span key={user.email}>
      <CustomPopover title={user.name} customClassName="inline">
        <Avatar
          key={index}
          className="w-[1.8rem] h-[1.8rem]"
          src={
            <Image
              preview={false}
              src="/images/drawer/memoji.png"
              alt="memoji"
              className="w-full h-full rounded-full"
              style={{
                padding: "1px",
              }}
            />
          }
          style={{
            backgroundColor: user.color || "transparent", // Set transparent if no color is provided
          }}
        />
      </CustomPopover>
    </span>
  ));

  return (
    <Avatar.Group
      className="flex items-center justify-center"
      max={{
        count: 2,
        style: {
          color: "#EEEEEE",
          backgroundColor: "#29292B",
        },
      }}
      shape="circle"
    >
      {usersArray}
    </Avatar.Group>
  );
}
