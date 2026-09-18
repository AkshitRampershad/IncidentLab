import { FlatCompat } from "@eslint/eslintrc";

const compat = new FlatCompat({ baseDirectory: import.meta.dirname });

const eslintConfig = [
  { ignores: ["next-env.d.ts"] }, // Next.js-generated, gitignored, "should not be edited"
  ...compat.extends("next/core-web-vitals", "next/typescript"),
];

export default eslintConfig;
