import logging
import os
from app import db, Lesson, Course
from video_utils import get_video_duration_v1
from natsort import natsorted

# Configuração de logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

def list_and_register_lessons(course_path, course_id):
    """
    Função que reprocessa o diretório do curso e atualiza as lições no banco de dados.
    Ela atualiza as lições existentes para manter o progresso e adiciona as novas.
    """
    # Obtém as lições existentes para o curso
    existing_lessons = {lesson.hierarchy_path: lesson for lesson in Lesson.query.filter_by(course_id=course_id).all()}

    lessons_to_add_or_update = []
    list_and_register_lessons_in_directory(course_path, course_id, lessons_to_add_or_update, existing_lessons)

    # Salva as lições atualizadas ou adicionadas ao banco de dados
    db.session.bulk_save_objects(lessons_to_add_or_update)
    db.session.commit()
    logging.info(f'Lições registradas/atualizadas com sucesso para o curso: {course_id}')

def list_and_register_lessons_in_directory(directory, course_id, lessons_to_add_or_update, existing_lessons, hierarchy_prefix=""):
    """
    Função que percorre recursivamente o diretório do curso e registra ou atualiza as lições no banco de dados.
    Essa função lida com arquivos de vídeo, PDF e outros tipos suportados.
    """
    for entry in natsorted(os.scandir(directory), key=lambda e: e.name):
        if entry.is_dir():
            # Se for um diretório, faz a chamada recursiva
            new_hierarchy_prefix = f"{hierarchy_prefix}/{entry.name}" if hierarchy_prefix else entry.name
            list_and_register_lessons_in_directory(entry.path, course_id, lessons_to_add_or_update, existing_lessons, new_hierarchy_prefix)
        elif entry.is_file() and entry.name.lower().endswith((".mp4", ".avi", ".ts", ".mov", ".wmv", ".flv", ".mkv", ".webm", ".pdf", ".txt", "html")):
            # Se for um arquivo suportado, cria ou atualiza a lição
            title = os.path.splitext(entry.name)[0]
            is_pdf = entry.name.lower().endswith(".pdf")
            duration = get_video_duration_v1(entry.path) if not is_pdf else 0

            # Verifica se a lição já existe com base no caminho hierárquico
            existing_lesson = existing_lessons.get(hierarchy_prefix)

            if existing_lesson:
                # Se a lição já existe, atualize apenas os dados relevantes (como o caminho do vídeo)
                existing_lesson.video_url = "" if is_pdf else entry.path
                existing_lesson.pdf_url = entry.path if is_pdf else ""
                existing_lesson.duration = str(duration)
                lessons_to_add_or_update.append(existing_lesson)
                logging.info(f'Atualizando lição existente: {title} - {entry.path}')
            else:
                # Se a lição não existe, cria uma nova
                lesson = Lesson(
                    course_id=course_id,
                    title=title,
                    module=hierarchy_prefix,
                    hierarchy_path=hierarchy_prefix,
                    video_url="" if is_pdf else entry.path,
                    duration=str(duration),
                    progressStatus='not_started',
                    isCompleted=0,
                    time_elapsed='0',
                    pdf_url=entry.path if is_pdf else ""
                )
                lessons_to_add_or_update.append(lesson)
                logging.info(f'Registrando nova lição: {title} - {entry.path}')

def scan_data_directory_and_register_courses():
    """
    Função que escaneia o diretório principal e registra novos cursos no banco de dados.
    Só registra cursos que ainda não estão no banco de dados.
    """
    # Obtém os cursos já registrados no banco
    existing_courses = {course.path for course in Course.query.all()}
    courses_to_add = []

    # Percorre o diretório de cursos (/data) e registra novos cursos
    for entry in os.scandir('/data'):
        if entry.is_dir() and entry.path not in existing_courses:
            course = Course(
                name=entry.name,
                path=entry.path,
                isCoverUrl=0,
                fileCover=None,
                urlCover=None
            )
            courses_to_add.append(course)

    # Se encontrar cursos novos, adiciona ao banco
    if courses_to_add:
        db.session.bulk_save_objects(courses_to_add)
        db.session.commit()

        # Registra as lições para os cursos encontrados
        for course in courses_to_add:
            list_and_register_lessons_in_directory(course.path, course.id)

        logging.info(f'Novos cursos registrados: {len(courses_to_add)}')
