import { Component, type ErrorInfo, type ReactNode } from "react";

interface ErrorBoundaryProps {
  children: ReactNode;
}

interface ErrorBoundaryState {
  error: Error | null;
}

export default class ErrorBoundary extends Component<
  ErrorBoundaryProps,
  ErrorBoundaryState
> {
  state: ErrorBoundaryState = { error: null };

  static getDerivedStateFromError(error: Error): ErrorBoundaryState {
    return { error };
  }

  componentDidCatch(error: Error, info: ErrorInfo) {
    console.error("Dashboard crashed:", error, info.componentStack);
  }

  render() {
    if (this.state.error) {
      return (
        <main className="dashboard crash-screen">
          <h2>Something went wrong</h2>
          <p>The dashboard hit an unexpected error: {this.state.error.message}</p>
          <button
            className="reset-filters"
            onClick={() => window.location.reload()}
          >
            Reload
          </button>
        </main>
      );
    }

    return this.props.children;
  }
}
