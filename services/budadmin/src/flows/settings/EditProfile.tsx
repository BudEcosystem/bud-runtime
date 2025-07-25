
import DrawerCard from "@/components/ui/bud/card/DrawerCard";
import DrawerTitleCard from "@/components/ui/bud/card/DrawerTitleCard";
import { BudWraperBox } from "@/components/ui/bud/card/wraperBox";

import { BudDrawerLayout } from "@/components/ui/bud/dataEntry/BudDrawerLayout";
import { BudForm } from "@/components/ui/bud/dataEntry/BudForm";
import ProjectNameInput from "@/components/ui/bud/dataEntry/ProjectNameInput";
import React, { useContext, useEffect, useState } from "react";
import { useDrawer } from "src/hooks/useDrawer";
import { BudFormContext } from "@/components/ui/bud/context/BudFormContext";
import { useUser } from "src/stores/useUser";
import { CustomPasswordInput } from "../components/CustomPasswordInput";

export default function EditProfile() {
  const { closeDrawer } = useDrawer();
  const { user, updateCurrentUser } = useUser();
  const { form, submittable } = useContext(BudFormContext);


  return (
    <BudForm
      data={{
        name: user?.name,
        description: "",
        tags: [],
        icon: ""
      }}
      disableNext={
        !submittable ||
        (form.getFieldValue("password") && form.getFieldValue("password") !== form.getFieldValue("repassword")) ||
        (!form.getFieldValue("password") && user?.name === form.getFieldValue("name"))
      }
      onNext={(values) => {
        if (submittable) {
          updateCurrentUser(
            {
              name: values.name,
              password: values.password,
            },
            user?.id
          ).then(() => {
            form.resetFields();
            closeDrawer();
          }
          )
          return;
        };
      }}
      nextText="Next"
    >
      <BudWraperBox center>
        <BudDrawerLayout>
          <DrawerTitleCard
            title="Edit Profile"
            description="Edit profile information below"
          />
          <DrawerCard classNames="pb-0">
            <ProjectNameInput
              placeholder="Enter Name"
              onChangeName={(name) => form.setFieldsValue({ name })}
              onChangeIcon={(icon) => form.setFieldsValue({ icon })}
              isEdit={true}
            />
            <div className="mt-[1.5rem] w-[full%] flex flex-col gap-[1.3rem]">
              <CustomPasswordInput
                name="password"
                label="Password"
                placeholder="Enter Password"
                onChange={(value) => form.setFieldsValue({ password: value })}
                rules={[
                  { required: false, message: "Please enter your password" },
                  { pattern: /^(?=.*[A-Z])(?=.*\d)(?=.*[@$!%*?&])[A-Za-z\d@$!%*?&]{8,}$/, message: "Password must be at least 8 characters long, include one uppercase letter, one number, and one special character (@$!%*?&)." },
                ]}
                inputStyle={{ paddingTop: ".37rem", paddingBottom: ".37rem", fontSize: ".75rem", fontWeight: 300 }}
              />
              <CustomPasswordInput
                name="repassword"
                label="Re-enter Password"
                placeholder="Re-enter Password"
                onChange={(value) => form.setFieldsValue({ repassword: value })}
                rules={[
                  {
                    validator(_, value) {
                      const password = form.getFieldValue("password");
                      if (!password && !value) {
                        // Both are empty: skip validation
                        return Promise.resolve();
                      }
                      if (password && !value) {
                        return Promise.reject(new Error("Please re-enter your password"));
                      }
                      if (password !== value) {
                        return Promise.reject(new Error("Passwords do not match"));
                      }
                      return Promise.resolve();
                    },
                  },
                ]}
                inputStyle={{ paddingTop: ".37rem", paddingBottom: ".37rem", fontSize: ".75rem", fontWeight: 300 }}
              />
            </div>
          </DrawerCard>
        </BudDrawerLayout>
      </BudWraperBox>
    </BudForm>
  );
}
