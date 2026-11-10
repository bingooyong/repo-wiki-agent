"""Round 25 (Nov 9 acceptance): one yardstick for the route cross-check and the gold routes.

Pages that list every business route must not fail the cross-check because of mount prefixes
(``/api``, ``/v1``), cross-file Go route groups, Express ``app.use`` mounts, or routes a library
adds by itself (flasgger ``/apidocs`` + spec route, FastAPI docs)."""

from __future__ import annotations

from repo_wiki.verifier.handbook_routes import (
    ROUTE_COMPLETENESS_MIN,
    extract_source_http_paths,
    handbook_route_crosscheck_mismatches,
    library_http_paths,
    route_completeness_ratio,
)

GO_FILES = [
    (
        "cmd/server/main.go",
        "package main\n"
        "func buildHandler() http.Handler {\n"
        "\trouter := routing.New()\n"
        '\trouter.Get("/healthcheck", healthcheck.Handler)\n'
        '\trg := router.Group("/v1")\n'
        "\tauthHandler := auth.Handler(cfg.JWTSigningKey)\n"
        '\talbum.RegisterHandlers(rg.Group(""),\n'
        "\t\talbum.NewService(album.NewRepository(db, logger), logger),\n"
        "\t\tauthHandler, logger,\n"
        "\t)\n"
        '\tauth.RegisterHandlers(rg.Group(""),\n'
        "\t\tauth.NewService(cfg.JWTSigningKey, cfg.JWTExpiration, logger),\n"
        "\t\tlogger,\n"
        "\t)\n"
        "\treturn router\n"
        "}\n",
    ),
    (
        "internal/album/api.go",
        "package album\n"
        "func RegisterHandlers(r *routing.RouteGroup, service Service, authHandler routing.Handler, logger log.Logger) {\n"
        "\tres := resource{service, logger}\n"
        '\tr.Get("/albums/<id>", res.get)\n'
        '\tr.Get("/albums", res.query)\n'
        "\tr.Use(authHandler)\n"
        '\tr.Post("/albums", res.create)\n'
        '\tr.Put("/albums/<id>", res.update)\n'
        '\tr.Delete("/albums/<id>", res.delete)\n'
        "}\n",
    ),
    (
        "internal/auth/api.go",
        "package auth\n"
        "func RegisterHandlers(rg *routing.RouteGroup, service Service, logger log.Logger) {\n"
        '\trg.Post("/login", login(service, logger))\n'
        "}\n",
    ),
]

GO_PAGE = (
    "## 接口\n\n所有业务接口都挂在 `/v1` 前缀下。\n\n"
    "接口 `GET /healthcheck`。\n接口 `GET /v1/albums`。\n接口 `GET /v1/albums/:id`。\n"
    "接口 `POST /v1/albums`。\n接口 `PUT /v1/albums/:id`。\n接口 `DELETE /v1/albums/:id`。\n"
    "接口 `POST /v1/login`。\n相册接口集中在 `/v1/albums` 下。\n"
)


def test_go_route_group_passed_to_another_package_carries_its_prefix() -> None:
    src = extract_source_http_paths(GO_FILES)
    norm = {(m, p.replace("<id>", ":id")) for m, p in src}
    assert ("GET", "/v1/albums") in norm
    assert ("DELETE", "/v1/albums/:id") in norm
    assert ("POST", "/v1/login") in norm
    assert ("GET", "/healthcheck") in norm
    assert ("GET", "/albums") not in norm  # no un-prefixed ghost copy


def test_go_page_with_full_routes_and_prefix_mentions_passes_crosscheck() -> None:
    assert handbook_route_crosscheck_mismatches(GO_PAGE, GO_FILES, api_page=True) == []
    assert route_completeness_ratio(GO_PAGE, GO_FILES) == 1.0


NODE_FILES = [
    (
        "src/app.js",
        "const express = require('express');\n"
        "const { authLimiter } = require('./middlewares/rateLimiter');\n"
        "const routes = require('./routes/v1');\n"
        "const app = express();\n"
        "app.use(express.json());\n"
        "if (config.env === 'production') {\n"
        "  app.use('/v1/auth', authLimiter);\n"
        "}\n"
        "app.use('/v1', routes);\n"
        "module.exports = app;\n",
    ),
    (
        "src/routes/v1/index.js",
        "const express = require('express');\n"
        "const authRoute = require('./auth.route');\n"
        "const userRoute = require('./user.route');\n"
        "const docsRoute = require('./docs.route');\n"
        "const router = express.Router();\n"
        "const defaultRoutes = [\n"
        "  {\n    path: '/auth',\n    route: authRoute,\n  },\n"
        "  {\n    path: '/users',\n    route: userRoute,\n  },\n"
        "];\n"
        "const devRoutes = [\n  {\n    path: '/docs',\n    route: docsRoute,\n  },\n];\n"
        "defaultRoutes.forEach((route) => {\n  router.use(route.path, route.route);\n});\n"
        "devRoutes.forEach((route) => {\n  router.use(route.path, route.route);\n});\n"
        "module.exports = router;\n",
    ),
    (
        "src/routes/v1/auth.route.js",
        "const express = require('express');\n"
        "const router = express.Router();\n"
        "router.post('/register', validate(authValidation.register), authController.register);\n"
        "router.post('/login', validate(authValidation.login), authController.login);\n"
        "module.exports = router;\n",
    ),
    (
        "src/routes/v1/user.route.js",
        "const express = require('express');\n"
        "const router = express.Router();\n"
        "router\n"
        "  .route('/')\n"
        "  .post(auth('manageUsers'), validate(userValidation.createUser), userController.createUser)\n"
        "  .get(auth('getUsers'), validate(userValidation.getUsers), userController.getUsers);\n"
        "router\n"
        "  .route('/:userId')\n"
        "  .get(auth('getUsers'), validate(userValidation.getUser), userController.getUser)\n"
        "  .patch(auth('manageUsers'), validate(userValidation.updateUser), userController.updateUser)\n"
        "  .delete(auth('manageUsers'), validate(userValidation.deleteUser), userController.deleteUser);\n"
        "module.exports = router;\n",
    ),
    (
        "src/routes/v1/docs.route.js",
        "const express = require('express');\n"
        "const swaggerUi = require('swagger-ui-express');\n"
        "const router = express.Router();\n"
        "router.use('/', swaggerUi.serve);\n"
        "router.get(\n  '/',\n  swaggerUi.setup(specs, {\n    explorer: true,\n  })\n);\n"
        "module.exports = router;\n",
    ),
]

NODE_GOLD = [
    ("POST", "/v1/auth/register"),
    ("POST", "/v1/auth/login"),
    ("POST", "/v1/users"),
    ("GET", "/v1/users"),
    ("GET", "/v1/users/:userId"),
    ("PATCH", "/v1/users/:userId"),
    ("DELETE", "/v1/users/:userId"),
    ("GET", "/v1/docs"),
]


def test_express_use_mounts_and_route_tables_compose_full_paths() -> None:
    src = extract_source_http_paths(NODE_FILES)
    for pair in NODE_GOLD:
        assert pair in src, (pair, sorted(src))
    assert ("POST", "/login") not in src


def test_express_page_with_full_routes_passes_crosscheck() -> None:
    page = "## 接口\n\n接口统一挂在 `/v1` 下。\n\n" + "\n".join(
        f"接口 `{m} {p}`。" for m, p in NODE_GOLD
    )
    assert handbook_route_crosscheck_mismatches(page, NODE_FILES, api_page=True) == []
    assert route_completeness_ratio(page, NODE_FILES) == 1.0


FASTAPI_FILES = [
    (
        "app/main.py",
        "from fastapi import FastAPI\n"
        "from app.api.routes.api import router as api_router\n"
        "def get_application() -> FastAPI:\n"
        "    application = FastAPI(**settings.fastapi_kwargs)\n"
        "    application.include_router(api_router, prefix=settings.api_prefix)\n"
        "    return application\n"
        "app = get_application()\n",
    ),
    ("app/core/settings/app.py", 'class AppSettings:\n    api_prefix: str = "/api"\n'),
    (
        "app/api/routes/api.py",
        "from fastapi import APIRouter\n"
        "from app.api.routes import tags\n"
        "router = APIRouter()\n"
        'router.include_router(tags.router, tags=["tags"], prefix="/tags")\n',
    ),
    (
        "app/api/routes/tags.py",
        "from fastapi import APIRouter\n"
        "router = APIRouter()\n"
        '@router.get("", name="tags:get-all")\n'
        "async def get_all_tags():\n    return {}\n",
    ),
]


def test_fastapi_bare_mount_prefix_mention_is_not_a_missing_route() -> None:
    page = "## 接口\n\n所有接口位于 `/api` 前缀下。\n\n接口 `GET /api/tags`。\n"
    assert ("GET", "/api/tags") in extract_source_http_paths(FASTAPI_FILES)
    assert handbook_route_crosscheck_mismatches(page, FASTAPI_FILES, api_page=True) == []


def test_unknown_prefix_or_invented_route_still_fails() -> None:
    page = "## 接口\n\n接口 `GET /api/secret`。\n前缀 `/internal` 下另有接口。\n"
    bad = handbook_route_crosscheck_mismatches(page, FASTAPI_FILES, api_page=True)
    assert "GET /api/secret" in bad and "ANY /internal" in bad
    # a method claim on a bare prefix is still a route claim, not a prefix mention
    assert handbook_route_crosscheck_mismatches("接口 `GET /api`。", FASTAPI_FILES, api_page=True)


FLASK_FILES = [
    (
        "src/config.py",
        'APPLICATION_ROOT = os.getenv("APPLICATION_APPLICATION_ROOT", "/application")\n',
    ),
    (
        "src/routes/user.py",
        "from flask import Blueprint\nfrom flask_restful import Api\n"
        'USER_BLUEPRINT = Blueprint("user", __name__)\n'
        'Api(USER_BLUEPRINT).add_resource(\n    UserResource, "/user/<string:last_name>/<string:first_name>"\n)\n',
    ),
    (
        "src/server.py",
        "from flasgger import Swagger\nfrom flask import Flask\n"
        "server = Flask(__name__)\n"
        'server.config["SWAGGER"] = {\n'
        '    "swagger_version": "2.0",\n'
        '    "specs": [\n'
        '        {\n'
        '            "version": "0.0.1",\n'
        '            "endpoint": "spec",\n'
        '            "route": "/application/spec",\n'
        "        }\n"
        "    ],\n"
        '    "static_url_path": "/apidocs",\n'
        "}\n"
        "Swagger(server)\n"
        "for blueprint in vars(routes).values():\n"
        "    if isinstance(blueprint, Blueprint):\n"
        "        server.register_blueprint(blueprint, url_prefix=config.APPLICATION_ROOT)\n",
    ),
]


def test_flasgger_routes_are_library_routes_allowed_on_the_page() -> None:
    lib = library_http_paths(FLASK_FILES)
    assert ("GET", "/application/spec") in lib and ("GET", "/apidocs") in lib
    page = (
        "## 接口\n\n接口 `GET /application/user/:last_name/:first_name`。\n"
        "接口 `POST /application/user/:last_name/:first_name`。\n"
        "Swagger 规范位于 `GET /application/spec`，文档页面为 `/apidocs`。\n"
    )
    assert handbook_route_crosscheck_mismatches(page, FLASK_FILES, api_page=True) == []
    # library routes never become required business routes
    assert route_completeness_ratio(page, FLASK_FILES) >= ROUTE_COMPLETENESS_MIN
    assert ("GET", "/apidocs") not in extract_source_http_paths(FLASK_FILES)


def test_fastapi_default_docs_routes_are_library_routes() -> None:
    lib = library_http_paths(FASTAPI_FILES)
    assert {("GET", "/docs"), ("GET", "/openapi.json")} <= lib
