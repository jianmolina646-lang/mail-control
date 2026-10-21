import { describe, it, expect } from "vitest";
import { filterPickerAccounts } from "./account-picker";
import type { MailAccount } from "@/lib/mail-data";
const make = (id:string, email:string, provider:MailAccount["provider"], alias="") => ({id,email,provider,alias} as MailAccount);
const accounts = [make("1","z@gmail.com","gmail","Ventas"),make("2","a@hotmail.com","hotmail"),make("3","b@live.com","live"),make("4","c@outlook.com","outlook")];
describe("account selector", () => {
 it("sorts without changing original data", () => {expect(filterPickerAccounts(accounts,"","all").map(a=>a.id)).toEqual(["2","3","4","1"]);expect(accounts[0].id).toBe("1");});
 it("searches address and alias ignoring case and outside whitespace", () => {expect(filterPickerAccounts(accounts," VENTAS ","all").map(a=>a.id)).toEqual(["1"]);expect(filterPickerAccounts(accounts,"HOTMAIL","all").map(a=>a.id)).toEqual(["2"]);});
 it("groups Microsoft accounts including Hotmail and Live", () => {expect(filterPickerAccounts(accounts,"","microsoft")).toHaveLength(3);expect(filterPickerAccounts(accounts,"","gmail")).toHaveLength(1);});
 it("combines query and provider and handles empty results", () => {expect(filterPickerAccounts(accounts,"hotmail","gmail")).toEqual([]);expect(filterPickerAccounts([],"","all")).toEqual([]);});
});
