import { AuthProvider } from "@/contexts/auth-context";
import { LanguageProvider } from "@/contexts/language-context";
import { ClientOnly } from "@/components/ClientOnly";

interface ProviderProps {
    children: React.ReactNode;
}
const Provider = ({ children }: ProviderProps) => {
    return (
        <LanguageProvider>
            <AuthProvider>
                <ClientOnly>{children}</ClientOnly>
            </AuthProvider>
        </LanguageProvider>
    );
};
export default Provider;
