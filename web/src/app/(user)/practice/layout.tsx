export default function PracticeLayout({
    children,
}: {
    children: React.ReactNode;
}) {
    return (
        <div className="relative flex flex-col h-screen w-full bg-slate-50 overflow-hidden">
            {/* Immersive background or specific practice background can go here */}
            <div className="flex-1 w-full h-full">
                {children}
            </div>
        </div>
    );
}
