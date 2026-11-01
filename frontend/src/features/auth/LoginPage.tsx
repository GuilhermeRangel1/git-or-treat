import { useState, type FormEvent } from "react";
import {
  ArrowRight,
  LockKeyhole,
  Eye,
  EyeOff,
  LoaderCircle,
  Moon,
  Sun,
  Zap,
} from "lucide-react";
import { Navigate, useNavigate } from "react-router-dom";
import { useSession } from "@/shared/auth/useSession";
import { useTheme } from "@/shared/theme/useTheme";
import Brand from "@/shared/ui/Brand";
import logoDark from "@/shared/ui/assets/grid360-dark.svg";
import logoLight from "@/shared/ui/assets/grid360-light.svg";
import EnergyArtwork from "./EnergyArtwork";
import { useReducedMotion } from "./useReducedMotion";
import "./login.css";

const currentYear = new Date().getFullYear();

export default function LoginPage() {
  const {
    configured,
    loading,
    user,
    login,
    error: sessionError,
  } = useSession();
  const { theme, toggleTheme } = useTheme();
  const navigate = useNavigate();
  const reducedMotion = useReducedMotion();
  const [username, setUsername] = useState("");
  const [password, setPassword] = useState("");
  const [showPassword, setShowPassword] = useState(false);
  const [pending, setPending] = useState(false);
  const [error, setError] = useState<string | null>(null);

  if (!loading && (user || (!configured && !sessionError)))
    return <Navigate to="/panorama" replace />;

  async function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (pending) return;
    const normalizedUsername = username.trim();
    if (!normalizedUsername || !password) {
      setError("Informe seu usuário e sua senha.");
      return;
    }
    setPending(true);
    setError(null);
    try {
      await login(normalizedUsername, password);
      setPassword("");
      navigate("/panorama", { replace: true });
    } catch (cause) {
      setError(
        cause instanceof Error
          ? cause.message
          : "Não foi possível entrar. Tente novamente.",
      );
    } finally {
      setPending(false);
    }
  }

  return (
    <div
      className="auth-login"
      data-motion={reducedMotion ? "paused" : "running"}
    >
      <a className="skip-link" href="#login-form">
        Ir para o formulário
      </a>
      <header className="site-header flex items-center justify-between gap-4">
        <div
          className="brand-lockup flex items-center gap-2.5"
          aria-label="Grid 360, V-Energy"
        >
          <Brand />
          <span className="brand-divider" />
          <span className="brand-parent eyebrow">V-ENERGY</span>
        </div>
        <div className="header-actions flex items-center gap-4">
          <span className="experiment-badge eyebrow">
            GRID <span>/</span> 360°
          </span>
          <button
            className="icon-button theme-toggle"
            type="button"
            aria-label={
              theme === "dark" ? "Ativar tema claro" : "Ativar tema escuro"
            }
            onClick={toggleTheme}
          >
            {theme === "dark" ? (
              <Sun size={19} strokeWidth={1.75} aria-hidden="true" />
            ) : (
              <Moon size={19} strokeWidth={1.75} aria-hidden="true" />
            )}
          </button>
        </div>
      </header>

      <main className="login-layout">
        <section
          className="story-panel"
          aria-label="Energia que conecta perspectivas"
        >
          <div className="energy-scene">
            <div className="scene-halo" aria-hidden="true" />
            <div className="scene-orbit orbit-one" aria-hidden="true" />
            <div className="scene-orbit orbit-two" aria-hidden="true" />
            <img
              className="energy-fallback"
              src={theme === "dark" ? logoDark : logoLight}
              alt=""
            />
            <EnergyArtwork
              theme={theme}
              logoSrc={theme === "dark" ? logoDark : logoLight}
              reducedMotion={reducedMotion}
            />
            <span className="scene-cross cross-left" aria-hidden="true">
              +
            </span>
            <span className="scene-cross cross-right" aria-hidden="true">
              +
            </span>
          </div>
          <div className="story-copy">
            <span className="eyebrow story-overline">
              ENERGIA. DADOS. POSSIBILIDADES.
            </span>
            <h2>
              Cada conexão, <br />
              uma nova <span>perspectiva.</span>
            </h2>
            <p>
              Transforme pontos de informação em uma visão
              <br className="desktop-break" /> mais clara do que move o seu
              negócio.
            </p>
          </div>
        </section>

        <section
          id="login-form"
          className="login-panel"
          aria-label="Entrar no Grid 360"
        >
          <div className="form-content">
            <div className="form-intro">
              <div className="welcome-mark">
                <LockKeyhole size={21} strokeWidth={1.5} aria-hidden="true" />
              </div>
              <span className="eyebrow">BEM-VINDO AO GRID 360</span>
              <h1>
                Um novo olhar <br />
                começa aqui.
              </h1>
              <p>Conecte-se à visão completa da sua energia.</p>
            </div>
            <form
              onSubmit={(event) => void submit(event)}
              noValidate
              aria-label="Entrar"
              aria-busy={pending}
            >
              <div className="field">
                <label htmlFor="username">Usuário</label>
                <div
                  className={`input-shell ${error && !username.trim() ? "has-error" : ""}`}
                >
                  <span className="login-user-icon" aria-hidden="true">
                    @
                  </span>
                  <input
                    id="username"
                    name="username"
                    type="text"
                    autoComplete="username"
                    autoCapitalize="none"
                    spellCheck={false}
                    placeholder="Seu usuário"
                    value={username}
                    disabled={pending}
                    aria-invalid={Boolean(error && !username.trim())}
                    onChange={(event) => {
                      setUsername(event.target.value);
                      setError(null);
                    }}
                  />
                </div>
              </div>
              <div className="field">
                <label htmlFor="password">Senha</label>
                <div
                  className={`input-shell ${error && !password ? "has-error" : ""}`}
                >
                  <LockKeyhole
                    size={18}
                    strokeWidth={1.75}
                    aria-hidden="true"
                  />
                  <input
                    id="password"
                    name="password"
                    type={showPassword ? "text" : "password"}
                    autoComplete="current-password"
                    placeholder="Digite sua senha"
                    value={password}
                    disabled={pending}
                    aria-invalid={Boolean(error && !password)}
                    onChange={(event) => {
                      setPassword(event.target.value);
                      setError(null);
                    }}
                  />
                  <button
                    className="password-toggle"
                    type="button"
                    aria-label={
                      showPassword ? "Ocultar senha" : "Mostrar senha"
                    }
                    aria-pressed={showPassword}
                    disabled={pending}
                    onClick={() => setShowPassword((visible) => !visible)}
                  >
                    {showPassword ? (
                      <EyeOff size={18} strokeWidth={1.75} aria-hidden="true" />
                    ) : (
                      <Eye size={18} strokeWidth={1.75} aria-hidden="true" />
                    )}
                  </button>
                </div>
              </div>
              {error || sessionError ? (
                <p className="login-error" role="alert">
                  {error ?? sessionError}
                </p>
              ) : null}
              <button
                className="primary-button"
                type="submit"
                disabled={pending}
              >
                {pending ? (
                  <>
                    Entrando
                    <LoaderCircle
                      size={18}
                      className="spinner"
                      aria-hidden="true"
                    />
                  </>
                ) : (
                  <>
                    Entrar
                    <ArrowRight size={18} aria-hidden="true" />
                  </>
                )}
              </button>
              <span className="sr-only" role="status">
                {pending ? "Verificando acesso. Aguarde." : ""}
              </span>
            </form>
            <div className="demo-disclaimer">
              <p>Use seu usuário e senha para acessar o Grid 360.</p>
            </div>
          </div>
          <div className="form-footnote">
            <Zap size={13} strokeWidth={1.5} aria-hidden="true" />
            <span>Uma visão completa. Uma energia nova.</span>
          </div>
        </section>
      </main>
      <footer className="page-footer flex flex-wrap items-center justify-between gap-3">
        <span>
          © {currentYear} V-Energy <span className="footer-separator">/</span>{" "}
          Grid 360
        </span>
        <span>Plataforma interna de inteligência energética</span>
      </footer>
    </div>
  );
}
