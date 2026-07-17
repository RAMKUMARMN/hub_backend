export async function discoverBackendArchitectureHandler() {
  return {
    content: [
      {
        type: "text" as const,
        text: JSON.stringify(
          {
            framework: "FastAPI",
            database: "SQLAlchemy",
            migrations: "Alembic",
            structure: [
              "app/models",
              "app/routers",
              "app/schemas",
              "app/services",
              "app/database.py",
              "app/config.py",
              "app/dependencies.py"
            ]
          },
          null,
          2
        ),
      },
    ],
  };
}