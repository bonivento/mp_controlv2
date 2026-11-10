// Protege las rutas cuando se usa Supabase: refresca la sesión (cookies) y envía
// a /login a quien no la tenga. En modo de demostración la sesión vive en el
// navegador (localStorage) y la protege el componente AuthGate del lado cliente.

import { createServerClient } from "@supabase/ssr";
import { NextResponse, type NextRequest } from "next/server";

const DEMO = process.env.NEXT_PUBLIC_DEMO_MODE === "1";
const URL_ = process.env.NEXT_PUBLIC_SUPABASE_URL ?? "";
const KEY = process.env.NEXT_PUBLIC_SUPABASE_ANON_KEY ?? "";

export async function proxy(request: NextRequest) {
  if (DEMO || !URL_ || !KEY) return NextResponse.next();

  let response = NextResponse.next({ request });
  const supabase = createServerClient(URL_, KEY, {
    cookies: {
      getAll: () => request.cookies.getAll(),
      setAll: (list) => {
        list.forEach(({ name, value }) => request.cookies.set(name, value));
        response = NextResponse.next({ request });
        list.forEach(({ name, value, options }) => response.cookies.set(name, value, options));
      },
    },
  });

  // getUser() valida el JWT con Supabase; getSession() solo lee la cookie.
  const { data } = await supabase.auth.getUser();
  const path = request.nextUrl.pathname;
  const isLogin = path === "/login";

  if (!data.user && !isLogin) {
    const url = request.nextUrl.clone();
    url.pathname = "/login";
    url.search = "";
    return NextResponse.redirect(url);
  }
  if (data.user && isLogin) {
    const url = request.nextUrl.clone();
    url.pathname = "/estudios";
    return NextResponse.redirect(url);
  }
  return response;
}

export const config = {
  // Todo menos la API (rewrite), recursos estáticos e imágenes.
  matcher: ["/((?!api|_next/static|_next/image|favicon.ico|.*\\.(?:svg|png|jpg|jpeg|gif|webp)$).*)"],
};
