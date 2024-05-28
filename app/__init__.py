import logging
import os
from http.client import HTTPException

from dotenv import load_dotenv
from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
from starlette.exceptions import HTTPException
from starlette.status import HTTP_404_NOT_FOUND

from app.core.exceptions import SettingNotFound
from app.core.init_app import (init_menus, init_superuser, make_middlewares,
                               register_db, register_exceptions,
                               register_routers)

logger = logging.getLogger("uvicorn")

try:
    from app.settings.config import settings
except ImportError:
    raise SettingNotFound("Can not import settings")


def load_static(app: FastAPI):
    """
    是否由FastAPI提供静态文件服务
    """
    app.mount("/", StaticFiles(directory="web/dist", html=True), name="dist")

    @app.exception_handler(HTTPException)
    async def _(request: Request, exc: HTTPException):
        # 检查异常的状态码是否为 404
        if exc.status_code == HTTP_404_NOT_FOUND:
            # 获取请求路径
            path = request.url.path
            # 检查路径是否不是以 /api 开头
            if not path.startswith("/api"):
                # 如果不是以 /api 开头，则重定向到根路径
                return RedirectResponse(url="/")
            # 如果是以 /api 开头，返回适当的 JSON 错误信息
            return JSONResponse(status_code=HTTP_404_NOT_FOUND, content={"detail": "Not Found"})
        # 对于其他的HTTP异常，返回JSON格式的错误详情
        return JSONResponse(status_code=exc.status_code, content={"detail": exc.detail})


def load_dotenv_file(app: FastAPI):
    """
    从环境变量中加载配置文件
    """
    # 是否由FastAPI提供静态文件服务
    if os.getenv("LOAD_STATIC_FROM_LOCAL") == "true":
        logger.info("使用FastAPI提供静态网页服务")
        load_static(app)
    else:
        logger.warning("未使用FastAPI提供静态网页服务,请单独启动静态网页服务!")

    # 使用的数据库类型
    db_type = os.getenv("DATABASE_TYPE")
    settings.TORTOISE_ORM = build_orm_config(db_type)


def build_orm_config(db_type: str):
    """
    构建ORM配置
    """
    if db_type == "mysql":
        logger.info("当前使用MySQL数据库")
        credentials = {
            "host": os.getenv("MYXQL_HOST"),
            "port": os.getenv("MYXQL_PORT"),
            "user": os.getenv("MYXQL_USER"),
            "password": os.getenv("MYXQL_PASSWORD"),
            "database": os.getenv("MYXQL_DATABASE"),
        }
    elif db_type == "sqlite":
        logger.info("当前使用SQLite数据库")
        credentials = {"file_path": f"{settings.BASE_DIR}/db.sqlite3"}
    else:
        db_type = "sqlite"
        logger.info("未提供数据库类型,默认使用使用SQLite数据库")
        credentials = {"file_path": f"{settings.BASE_DIR}/db.sqlite3"}

    return {
        "connections": {
            db_type: {
                "engine": f"tortoise.backends.{db_type}",
                "credentials": credentials,
            }
        },
        "apps": {
            "models": {
                "models": ["app.models"],
                "default_connection": db_type,
            },
        },
        "use_tz": False,
        "timezone": "Asia/Shanghai",
    }


def create_app() -> FastAPI:
    # 从环境变量中加载配置文件
    load_dotenv()

    app = FastAPI(
        title=settings.APP_TITLE,
        description=settings.APP_DESCRIPTION,
        version=settings.VERSION,
        openapi_url="/openapi.json",
        middleware=make_middlewares(),
    )

    load_dotenv_file(app)

    register_db(app)
    register_exceptions(app)
    register_routers(app, prefix="/api")
    return app


app = create_app()


@app.on_event("startup")
async def startup_event():
    await init_superuser()
    await init_menus()
