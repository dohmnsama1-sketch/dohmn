import { z } from "zod";

export const schema = z.unknown();
export type InputType = z.infer<typeof schema>;
export type OutputType = unknown;