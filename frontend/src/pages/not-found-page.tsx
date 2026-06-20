import { Link } from "react-router-dom";

import { buttonVariants } from "../components/ui/button-styles";

export function NotFoundPage() {
  return (
    <main className="flex min-h-screen flex-col items-center justify-center gap-4 bg-background px-4 text-center">
      <div>
        <p className="text-sm font-semibold uppercase text-primary">404</p>
        <h1 className="mt-2 text-2xl font-semibold">Page not found</h1>
        <p className="mt-2 text-sm text-muted-foreground">
          The requested OpenAlpha page is not available.
        </p>
      </div>
      <Link className={buttonVariants()} to="/">
        Dashboard
      </Link>
    </main>
  );
}
