export type Config = {
    apiUrl: string;
};
const configs: Config = {
    apiUrl: process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000",
};
export default configs;
