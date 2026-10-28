"""Онтология v2: атомарные навыки, категории и зависимости.

Источники:
- ``hr_ontology.ttl`` — 76 навыков, алиасы и примеры требований;
- ``skills_curated.csv`` — категории и частотные признаки.

TTL не содержит иерархии, уровней и пререквизитов: это SKOS-подобный словарь
навыков плюс свидетельства. Поэтому здесь добавлены категории, русские и
английские алиасы и граф ``REQUIRES``. Старые ключи v1 сохранены, чтобы
профили и планы, созданные до обновления, не потеряли связи с темами.

Онтология остаётся словарём, а не фильтром: незнакомые навыки сохраняются
в ``raw_name`` и попадают в кандидаты на новые темы.
"""

from dataclasses import dataclass, field

# Версия онтологии: повышается при изменении состава тем или зависимостей
ONTOLOGY_VERSION = 2


@dataclass(frozen=True)
class OntologyTopic:
    """Описание темы онтологии."""

    key: str
    name: str
    description: str
    category: str
    aliases: tuple[str, ...] = field(default_factory=tuple)
    prerequisites: tuple[str, ...] = field(default_factory=tuple)

    def alias_texts(self) -> tuple[str, ...]:
        """Названия, по которым навык сопоставляется с темой (включая ключ)."""
        return (self.key, self.name, *self.aliases)


# Спецификация: ключ, название, категория, описание, алиасы, пререквизиты.
# Одна строка на тему — так проще ревьюить состав и не терять зависимости.
TopicSpec = tuple[str, str, str, str, tuple[str, ...], tuple[str, ...]]

_TOPIC_SPECS: tuple[TopicSpec, ...] = (
    # --- Языки программирования и фундамент ---
    (
        "python",
        "Python",
        "language",
        (
            "Язык Python: синтаксис, типы данных, итераторы, генераторы, asyncio, "
            "пакеты, декораторы и тестирование."
        ),
        ("python3", "питон", "py", "python 3"),
        (),
    ),
    (
        "java",
        "Java",
        "language",
        (
            "Язык Java: синтаксис, ООП, коллекции, исключения, многопоточность, "
            "JVM и экосистема Spring."
        ),
        ("java se", "джава"),
        (),
    ),
    (
        "csharp",
        "C#",
        "language",
        "Язык C#: синтаксис, ООП, LINQ, async/await, .NET и типизация.",
        ("c sharp", "си шарп", "dotnet", ".net"),
        (),
    ),
    (
        "cpp",
        "C++",
        "language",
        ("Язык C++: синтаксис, память, указатели, STL, шаблоны и производительность."),
        ("c plus plus", "си плюс плюс"),
        (),
    ),
    (
        "javascript",
        "JavaScript",
        "language",
        ("Язык JavaScript: синтаксис, замыкания, прототипы, асинхронность, DOM и работа с API."),
        ("js", "java script", "джаваскрипт"),
        (),
    ),
    (
        "typescript",
        "TypeScript",
        "language",
        (
            "TypeScript: статическая типизация, интерфейсы, дженерики и "
            "интеграция с JavaScript-экосистемой."
        ),
        ("ts", "тайпскрипт"),
        ("javascript",),
    ),
    (
        "r",
        "R",
        "language",
        ("Язык R: статистика, анализ данных, визуализация и работа с data frame."),
        ("r language", "язык r"),
        (),
    ),
    (
        "swift",
        "Swift",
        "language",
        (
            "Язык Swift: синтаксис, опциональные типы, протоколы, async/await "
            "и разработка под Apple."
        ),
        ("свифт",),
        (),
    ),
    (
        "oop",
        "ООП и паттерны проектирования",
        "design",
        (
            "Объектно-ориентированное программирование: классы, наследование, "
            "композиция, SOLID, GRASP и паттерны проектирования."
        ),
        (
            "ооп",
            "объектно-ориентированное программирование",
            "design patterns",
            "паттерны проектирования",
            "solid",
        ),
        (),
    ),
    (
        "algorithms",
        "Алгоритмы и структуры данных",
        "algorithms",
        (
            "Алгоритмы и структуры данных: массивы, списки, деревья, графы, "
            "сортировка, поиск, big O и динамическое программирование."
        ),
        (
            "алгоритмы",
            "структуры данных",
            "dsa",
            "data structures and algorithms",
            "сложность алгоритмов",
            "big o",
        ),
        (),
    ),
    # --- Сети, API и архитектура ---
    (
        "http_api",
        "Сети, HTTP и REST API",
        "networking",
        (
            "HTTP, TCP/IP, REST, коды состояний, аутентификация, идемпотентность, "
            "кэширование и проектирование API."
        ),
        (
            "http",
            "rest",
            "rest api",
            "restful",
            "http-клиент",
            "web api",
            "api",
            "tcp/ip",
            "сетевое программирование",
        ),
        (),
    ),
    (
        "system_design",
        "Проектирование систем",
        "design",
        (
            "Проектирование backend-систем: границы сервисов, хранение данных, "
            "масштабирование, отказоустойчивость и компромиссы."
        ),
        ("system design", "проектирование систем", "архитектура приложений"),
        ("http_api", "databases"),
    ),
    (
        "microservices",
        "Микросервисы",
        "design",
        (
            "Микросервисная архитектура: декомпозиция, контракты, "
            "межсервисное взаимодействие, наблюдаемость и деплой."
        ),
        ("microservices", "микросервисы"),
        ("system_design", "docker"),
    ),
    # --- Данные и базы данных ---
    (
        "sql",
        "SQL",
        "data",
        (
            "Язык SQL: SELECT, JOIN, GROUP BY, подзапросы, оконные функции, "
            "индексы, планы запросов и нормализация."
        ),
        (
            "sql",
            "язык запросов",
            "sql запросы",
            "запросы sql",
            "select",
            "t-sql",
            "базовые запросы",
        ),
        (),
    ),
    (
        "databases",
        "Базы данных: проектирование и транзакции",
        "data",
        (
            "Проектирование схемы, нормализация, ACID, транзакции, уровни "
            "изоляции, MVCC, блокировки, репликация и партиционирование."
        ),
        (
            "бд",
            "база данных",
            "database design",
            "проектирование баз данных",
            "acid",
            "mvcc",
            "транзакции",
            "репликация",
        ),
        ("sql",),
    ),
    (
        "postgresql",
        "PostgreSQL",
        "database",
        (
            "PostgreSQL: диалект SQL, индексы, планы запросов, транзакции, "
            "расширения и администрирование."
        ),
        ("postgres", "psql", "постгрес"),
        ("sql",),
    ),
    (
        "mysql",
        "MySQL",
        "database",
        ("MySQL: диалект SQL, движки хранения, индексы, репликация и оптимизация запросов."),
        ("майскуэль",),
        ("sql",),
    ),
    (
        "mssql",
        "Microsoft SQL Server",
        "database",
        ("Microsoft SQL Server: T-SQL, индексы, планы выполнения, транзакции и администрирование."),
        ("mssql", "sql server", "ms sql"),
        ("sql",),
    ),
    (
        "oracle",
        "Oracle Database",
        "database",
        ("Oracle Database: SQL, PL/SQL, индексы, планы запросов и администрирование."),
        ("oracle database", "оракл"),
        ("sql",),
    ),
    (
        "mongodb",
        "MongoDB",
        "database",
        ("MongoDB: документная модель, запросы, индексы, агрегации и масштабирование."),
        ("mongo", "монго"),
        ("databases",),
    ),
    (
        "redis",
        "Redis",
        "database",
        ("Redis: key-value хранилище, структуры данных, кэширование, TTL и pub/sub."),
        ("редис",),
        ("databases",),
    ),
    (
        "data_engineering",
        "Инженерия данных",
        "data_platform",
        (
            "Инженерия данных: пайплайны, хранилища, качество данных, "
            "оркестрация и потоковая обработка."
        ),
        ("data engineering", "data engineer", "инженерия данных"),
        ("sql",),
    ),
    (
        "etl",
        "ETL",
        "data_platform",
        (
            "ETL/ELT: извлечение, трансформация и загрузка данных, "
            "инкрементальные пайплайны и контроль качества."
        ),
        ("etl tools", "etl pipelines", "etl пайплайны"),
        ("data_engineering",),
    ),
    (
        "kafka",
        "Apache Kafka",
        "data_platform",
        (
            "Apache Kafka: топики, партиции, consumer groups, гарантии "
            "доставки и потоковая обработка."
        ),
        ("apache kafka", "кафка"),
        ("data_engineering",),
    ),
    (
        "spark",
        "Apache Spark",
        "data_platform",
        (
            "Apache Spark: RDD, DataFrame, Spark SQL, планирование заданий "
            "и обработка больших данных."
        ),
        ("apache spark", "спарк"),
        ("data_engineering",),
    ),
    (
        "pyspark",
        "PySpark",
        "data_platform",
        ("PySpark: Python API для Spark, DataFrame, UDF и обработка больших наборов данных."),
        ("py spark",),
        ("python", "spark"),
    ),
    (
        "hadoop",
        "Apache Hadoop",
        "data_platform",
        ("Apache Hadoop: HDFS, MapReduce, YARN и хранение больших наборов данных."),
        ("hadoop", "хадуп"),
        ("data_engineering",),
    ),
    (
        "hive",
        "Apache Hive",
        "data_platform",
        ("Apache Hive: HiveQL, таблицы, партиционирование и аналитика поверх Hadoop."),
        ("hive", "хайв"),
        ("data_engineering",),
    ),
    # --- Анализ и визуализация данных ---
    (
        "statistics",
        "Статистика",
        "data",
        (
            "Статистика: описательные метрики, распределения, проверка "
            "гипотез, доверительные интервалы и A/B-тесты."
        ),
        ("statistical analysis", "статистика", "статистический анализ"),
        (),
    ),
    (
        "data_analysis",
        "Анализ данных",
        "data",
        (
            "Анализ данных: постановка вопроса, очистка, исследовательский "
            "анализ, метрики и интерпретация результатов."
        ),
        ("data analytics", "анализ данных", "аналитика данных", "аналитик данных"),
        ("statistics",),
    ),
    (
        "data_visualization",
        "Визуализация данных",
        "data",
        ("Визуализация данных: выбор графика, dashboards, читаемость, искажения и storytelling."),
        ("data visualisation", "визуализация данных"),
        ("statistics",),
    ),
    (
        "data_science",
        "Data Science",
        "ml",
        ("Data Science: полный цикл от данных и признаков до модели, метрик и внедрения."),
        ("data scientist", "наука о данных", "дата сайенс"),
        ("data_analysis", "ml"),
    ),
    (
        "ab_testing",
        "A/B-тестирование",
        "data",
        ("A/B-тесты: гипотезы, размер выборки, метрики, значимость и интерпретация экспериментов."),
        ("a/b testing", "a b testing", "a/b тесты", "ab тесты", "a b тесты"),
        ("statistics",),
    ),
    (
        "tableau",
        "Tableau",
        "data_platform",
        ("Tableau: подключение данных, расчётные поля, dashboards и интерактивная визуализация."),
        ("табло",),
        ("data_visualization",),
    ),
    (
        "power_bi",
        "Power BI",
        "data_platform",
        "Power BI: модели данных, DAX, отчёты, dashboards и публикация.",
        ("powerbi", "power bi", "повер би"),
        ("data_visualization",),
    ),
    # --- Машинное обучение ---
    (
        "ml",
        "Machine Learning",
        "ml",
        (
            "Машинное обучение: постановка задачи, признаки, обучение, "
            "валидация, метрики и переобучение."
        ),
        ("machine learning", "ml", "машинное обучение"),
        ("python", "statistics"),
    ),
    (
        "deep_learning",
        "Deep Learning",
        "ml",
        (
            "Глубокое обучение: нейронные сети, функции потерь, оптимизация, "
            "регуляризация и обучение на больших данных."
        ),
        ("deep learning", "dl", "глубокое обучение"),
        ("ml",),
    ),
    (
        "nlp",
        "Natural Language Processing",
        "ml",
        (
            "Обработка естественного языка: токенизация, эмбеддинги, "
            "классификация, NER и языковые модели."
        ),
        ("nlp", "обработка естественного языка"),
        ("ml",),
    ),
    (
        "computer_vision",
        "Computer Vision",
        "ml",
        ("Компьютерное зрение: изображения, свёртки, детекция, сегментация и метрики качества."),
        ("computer vision", "компьютерное зрение"),
        ("ml",),
    ),
    (
        "feature_engineering",
        "Feature Engineering",
        "ml",
        ("Feature engineering: признаки, кодирование, масштабирование, отбор и утечки данных."),
        ("feature engineering", "фича инжиниринг"),
        ("ml",),
    ),
    (
        "random_forest",
        "Random Forest",
        "ml",
        ("Random Forest: бэггинг, деревья решений, важность признаков и подбор гиперпараметров."),
        ("random forest", "случайный лес"),
        ("ml",),
    ),
    (
        "sklearn",
        "Scikit-learn",
        "ml_library",
        ("Scikit-learn: transformers, estimators, pipelines, кросс-валидация и метрики."),
        ("scikit learn", "scikit", "sklearn", "scikit-learn"),
        ("ml", "python"),
    ),
    (
        "tensorflow",
        "TensorFlow",
        "ml_library",
        ("TensorFlow: графы вычислений, Keras API, обучение и экспорт моделей."),
        ("tf", "тензорфлоу"),
        ("deep_learning", "python"),
    ),
    (
        "pytorch",
        "PyTorch",
        "ml_library",
        ("PyTorch: тензоры, autograd, модули, обучение и отладка нейронных сетей."),
        ("torch", "пайторч"),
        ("deep_learning", "python"),
    ),
    (
        "keras",
        "Keras",
        "ml_library",
        ("Keras: высокоуровневые слои, модели, обучение и интеграция с TensorFlow."),
        ("керас",),
        ("deep_learning", "python"),
    ),
    (
        "xgboost",
        "XGBoost",
        "ml_library",
        ("XGBoost: градиентный бустинг, деревья, регуляризация и подбор гиперпараметров."),
        ("xg boost",),
        ("ml", "python"),
    ),
    (
        "catboost",
        "CatBoost",
        "ml_library",
        ("CatBoost: градиентный бустинг, категориальные признаки и обучение моделей."),
        ("cat boost",),
        ("ml", "python"),
    ),
    (
        "numpy",
        "NumPy",
        "data_library",
        ("NumPy: массивы, векторизованные вычисления, broadcasting и работа с числовыми данными."),
        ("np",),
        ("python",),
    ),
    (
        "pandas",
        "Pandas",
        "data_library",
        ("Pandas: Series, DataFrame, очистка, группировки, join и анализ табличных данных."),
        ("пандас",),
        ("python",),
    ),
    (
        "matplotlib",
        "Matplotlib",
        "data_library",
        ("Matplotlib: графики, оси, стили, подграфики и сохранение визуализаций."),
        ("матплотлиб",),
        ("python", "data_visualization"),
    ),
    (
        "seaborn",
        "Seaborn",
        "data_library",
        ("Seaborn: статистические графики, распределения, категориальные диаграммы и стили."),
        ("сиборн",),
        ("python", "matplotlib"),
    ),
    (
        "jupyter",
        "Jupyter Notebook",
        "tools",
        ("Jupyter: интерактивные ноутбуки, ячейки, визуализация и воспроизводимые исследования."),
        ("jupyter notebook", "юпитер"),
        ("python",),
    ),
    # --- DevOps, облака и инфраструктура ---
    (
        "linux",
        "Linux",
        "devops",
        ("Linux: файловая система, процессы, права, bash, сеть и диагностика сервера."),
        ("unix", "линукс", "bash", "shell", "командная строка"),
        (),
    ),
    (
        "git",
        "Git и контроль версий",
        "process",
        (
            "Git: ветки, merge, rebase, разрешение конфликтов, история и "
            "командная работа с репозиторием."
        ),
        ("git", "система контроля версий", "version control"),
        (),
    ),
    (
        "github",
        "GitHub",
        "process",
        ("GitHub: репозитории, pull requests, issues, review и совместная работа над кодом."),
        ("github", "гитхаб"),
        ("git",),
    ),
    (
        "cicd",
        "CI/CD",
        "process",
        ("CI/CD: автоматическая сборка, тесты, деплой, пайплайны и качество поставки."),
        (
            "ci/cd",
            "ci cd",
            "continuous integration",
            "continuous delivery",
            "непрерывная интеграция",
            "github actions",
            "gitlab ci",
        ),
        ("git",),
    ),
    (
        "code_review",
        "Code Review",
        "process",
        ("Code review: чтение изменений, поиск дефектов, обратная связь и культура ревью."),
        ("code review", "код ревью", "ревью кода", "pull request", "pr review"),
        ("git",),
    ),
    (
        "docker",
        "Docker",
        "devops",
        ("Docker: образы, контейнеры, Dockerfile, тома, сети и воспроизводимая среда."),
        ("dockerfile", "docker образы", "контейнеры", "контейнеризация"),
        ("linux",),
    ),
    (
        "kubernetes",
        "Kubernetes",
        "devops",
        ("Kubernetes: pod, deployment, service, ingress, конфигурация и масштабирование."),
        ("k8s", "кубернетес", "кубер"),
        ("docker",),
    ),
    (
        "ansible",
        "Ansible",
        "devops",
        ("Ansible: inventory, playbooks, роли, идемпотентность и автоматизация конфигурации."),
        ("ансибл",),
        ("linux",),
    ),
    (
        "terraform",
        "Terraform",
        "devops",
        ("Terraform: провайдеры, ресурсы, state, модули и инфраструктура как код."),
        ("терраформ",),
        ("cloud",),
    ),
    (
        "devops",
        "DevOps",
        "devops",
        ("DevOps: культура и практики автоматизации поставки, наблюдаемости и эксплуатации."),
        ("devops", "девопс"),
        (),
    ),
    (
        "cloud",
        "Облачные технологии",
        "cloud",
        ("Облачные технологии: IaaS/PaaS, сети, хранение, безопасность и стоимость."),
        ("cloud", "cloud computing", "облачные технологии", "облака"),
        (),
    ),
    (
        "aws",
        "AWS",
        "cloud",
        "AWS: EC2, S3, IAM, VPC, базы данных и managed-сервисы.",
        ("amazon web services", "aws cloud", "амазон"),
        ("cloud",),
    ),
    (
        "azure",
        "Microsoft Azure",
        "cloud",
        ("Microsoft Azure: compute, storage, networking, identity и managed-сервисы."),
        ("azure", "ms azure"),
        ("cloud",),
    ),
    (
        "gcp",
        "Google Cloud",
        "cloud",
        ("Google Cloud: compute, storage, BigQuery, IAM и managed-сервисы."),
        ("gcp", "google cloud platform"),
        ("cloud",),
    ),
    # --- Web и мобильная разработка ---
    (
        "html",
        "HTML",
        "web",
        "HTML: семантика, формы, доступность и структура документа.",
        ("html5",),
        (),
    ),
    (
        "css",
        "CSS",
        "web",
        ("CSS: каскад, селекторы, layout, адаптивность и визуальное оформление."),
        ("css3",),
        (),
    ),
    (
        "react",
        "React",
        "web",
        ("React: компоненты, props, state, hooks, маршрутизация и работа с API."),
        ("reactjs", "react js", "реакт"),
        ("javascript", "html", "css"),
    ),
    (
        "nodejs",
        "Node.js",
        "web",
        ("Node.js: event loop, модули, HTTP-серверы, npm и асинхронный JavaScript."),
        ("node js", "нода"),
        ("javascript",),
    ),
    (
        "django",
        "Django",
        "web",
        ("Django: ORM, модели, views, шаблоны, админка и маршрутизация."),
        ("джанго",),
        ("python", "http_api"),
    ),
    (
        "flask",
        "Flask",
        "web",
        ("Flask: приложение, маршруты, шаблоны, расширения и REST API."),
        ("фласк",),
        ("python", "http_api"),
    ),
    (
        "fastapi",
        "FastAPI",
        "web",
        ("FastAPI: Pydantic-схемы, зависимости, async-обработчики, OpenAPI и тестирование."),
        ("fast api", "фастапи"),
        ("python", "http_api"),
    ),
    (
        "ios",
        "iOS",
        "mobile",
        ("iOS: платформа, lifecycle приложения, UIKit/SwiftUI и публикация в App Store."),
        ("айос",),
        ("swift",),
    ),
    (
        "swiftui",
        "SwiftUI",
        "mobile",
        ("SwiftUI: декларативные view, state, навигация и интеграция с UIKit."),
        ("swift ui", "свифт ui"),
        ("swift",),
    ),
    # --- Тестирование и качество ---
    (
        "testing",
        "Тестирование и качество кода",
        "quality",
        (
            "Тестирование: юнит-, интеграционные и e2e-тесты, pytest, "
            "фикстуры, моки, TDD, покрытие и тест-дизайн."
        ),
        (
            "тестирование",
            "unit testing",
            "unit-тесты",
            "pytest",
            "tdd",
            "покрытие кода",
            "тест-дизайн",
        ),
        (),
    ),
    # --- Офисные, инженерные и бизнес-навыки ---
    (
        "excel",
        "Microsoft Excel",
        "office",
        ("Excel: формулы, сводные таблицы, фильтры, диаграммы и анализ табличных данных."),
        ("microsoft excel", "ms excel", "эксель"),
        (),
    ),
    (
        "office",
        "Microsoft Office",
        "office",
        ("Microsoft Office: совместная работа с документами, таблицами и презентациями."),
        ("microsoft office suite", "ms office", "ms office suite", "офис"),
        (),
    ),
    (
        "outlook",
        "Microsoft Outlook",
        "office",
        ("Outlook: почта, календарь, задачи и организация коммуникации."),
        ("microsoft outlook", "ms outlook", "аутлук"),
        (),
    ),
    (
        "powerpoint",
        "Microsoft PowerPoint",
        "office",
        ("PowerPoint: структура презентации, слайды, диаграммы и визуальная подача."),
        ("power point", "ms powerpoint", "поверпоинт"),
        (),
    ),
    (
        "word",
        "Microsoft Word",
        "office",
        ("Word: структура документа, стили, оглавление, таблицы и оформление."),
        ("microsoft word", "ms word", "ворд"),
        (),
    ),
    (
        "ms_project",
        "MS Project",
        "office",
        ("MS Project: задачи, ресурсы, зависимости, календарь и контроль сроков."),
        ("microsoft project", "ms project"),
        (),
    ),
    (
        "project_management",
        "Управление проектами",
        "business",
        ("Управление проектами: scope, сроки, ресурсы, риски, коммуникации и контроль результата."),
        ("project management", "управление проектами", "проджект менеджмент"),
        (),
    ),
    (
        "hrm",
        "Human Resource Management",
        "business",
        ("HR-менеджмент: подбор, адаптация, оценка, развитие и управление персоналом."),
        ("human resource management", "hr management", "управление персоналом"),
        (),
    ),
    (
        "autocad",
        "AutoCAD",
        "engineering",
        ("AutoCAD: чертежи, слои, размеры, компоновка и подготовка проектной документации."),
        ("auto cad", "автокад"),
        (),
    ),
    (
        "civil3d",
        "Civil 3D",
        "engineering",
        ("Civil 3D: проектирование инфраструктуры, поверхности, трассы и профили."),
        ("civil 3d", "сивил 3d"),
        (),
    ),
    (
        "etabs",
        "ETABS",
        "engineering",
        ("ETABS: расчёт строительных конструкций, нагрузки, комбинации и анализ."),
        ("этабс",),
        (),
    ),
    (
        "solidworks",
        "SolidWorks",
        "engineering",
        ("SolidWorks: 3D-моделирование, сборки, чертежи и проектирование изделий."),
        ("solid works", "солидворкс"),
        (),
    ),
    (
        "ccna",
        "CCNA",
        "certification",
        ("CCNA: основы сетей, маршрутизация, коммутация, безопасность и диагностика Cisco."),
        ("ccna certification", "cisco certified network associate"),
        (),
    ),
)

ONTOLOGY_TOPICS: tuple[OntologyTopic, ...] = tuple(
    OntologyTopic(
        key=key,
        name=name,
        category=category,
        description=description,
        aliases=aliases,
        prerequisites=prerequisites,
    )
    for key, name, category, description, aliases, prerequisites in _TOPIC_SPECS
)


def topic_by_key(key: str) -> OntologyTopic | None:
    """Возвращает тему онтологии по ключу."""
    for topic in ONTOLOGY_TOPICS:
        if topic.key == key:
            return topic
    return None
