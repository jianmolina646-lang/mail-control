import { useState } from "react";
import { useNavigate } from "react-router-dom";
import { api, setToken } from "../lib/api";

export default function Login() {
  const nav = useNavigate();
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(false);

  const submit = async (e) => {
    e.preventDefault();
    setError("");
    setLoading(true);
    try {
      const { access_token } = await api.login(email, password);
      setToken(access_token);
      nav("/");
    } catch (err) {
      setError(err.message);
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="min-h-screen flex items-center justify-center p-4">
      <form
        onSubmit={submit}
        className="w-full max-w-sm bg-panel border border-edge rounded-2xl p-8 space-y-5"
      >
        <div className="text-center">
          <div className="text-4xl">👑</div>
          <h1 className="text-xl font-bold text-white mt-2">Mail Control</h1>
          <div className="text-xs tracking-widest text-gold">TEAM JHELIZ</div>
        </div>
        <input
          type="email"
          required
          placeholder="Email"
          value={email}
          onChange={(e) => setEmail(e.target.value)}
          className="w-full bg-surface border border-edge rounded-lg px-3 py-2.5 text-sm focus:outline-none focus:border-accent"
        />
        <input
          type="password"
          required
          placeholder="Contraseña"
          value={password}
          onChange={(e) => setPassword(e.target.value)}
          className="w-full bg-surface border border-edge rounded-lg px-3 py-2.5 text-sm focus:outline-none focus:border-accent"
        />
        {error && <div className="text-sm text-red-400">{error}</div>}
        <button
          disabled={loading}
          className="w-full bg-accent hover:bg-red-700 disabled:opacity-60 text-white font-semibold rounded-lg py-2.5 transition"
        >
          {loading ? "Entrando…" : "Entrar"}
        </button>
      </form>
    </div>
  );
}
