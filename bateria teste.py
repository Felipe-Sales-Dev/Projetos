import sys
import hid
import time
import threading
from pystray import Icon, Menu, MenuItem
from PIL import Image, ImageDraw, ImageFont

# Substitua pelos IDs do seu teclado (use lsusb ou Gerenciador de Dispositivos)
VENDOR_ID = 0x05AC   
PRODUCT_ID = 0x024F
INTERFACE = 3 
# ----------------------
INTERVALO_ATUALIZACAO = 10  # em segundos

# Variável para controlar o ícone na tray do windows
icon_app = None
ultimo_nivel_bateria = "--"

def criar_imagem_icone(texto, cor_fundo):
    """
    gera uma imagem quadrada 64x64 com o valor da bateria escrito em %.
    """
    # Nossa imagem vazia, sem cor alguma
    width = 64
    height = 64
    image = Image.new('RGBA', (width, height), (0, 0, 0, 0))
    draw = ImageDraw.Draw(image)
    
    #Definição de cores do texto
    cor_texto = (255, 255, 255, 255)  # Branco

    # Desenha um retângulo arredondado de fundo

    draw.rectangle(
        (0, 0, width, height),
        fill=cor_fundo,
        outline=None,
    )

    # Texto centralizado
    # Se quiser, troque o arial por outra fonte que tenha no seu sistema
    try:
        font = ImageFont.truetype("arial.ttf", 30)
    except:
        font = ImageFont.load_default()
    
    # Cálculos para centralizar o texto (bounding box)
    bbox = draw.textbbox((0,0), texto, font=font)
    text_w = bbox[2] - bbox[0]
    text_h = bbox[3] - bbox[1]
    draw.text(((width - text_w) / 2, (height - text_h) / 2 - 5), texto, font=font, fill=cor_texto)

    return image

def calcular_checksum(dados):
    """Soma os bytes para gerar o último byte do pacote (validade)."""
    return sum(dados) & 0xFF

def obter_nivel_bateria():
    
    dispositivos = hid.enumerate(VENDOR_ID, PRODUCT_ID)
    caminho_dispositivo = None
    
    for d in dispositivos:
        if d['interface_number'] == INTERFACE:
            caminho_dispositivo = d['path']
            break
            
    if not caminho_dispositivo:
        print(f"Erro: Interface {INTERFACE} não encontrada para este VID/PID.")
        return
    
    try:
        # 1. Abre o dispositivo
        device = hid.device()
        device.open_path(caminho_dispositivo)
        device.set_nonblocking(0) # Modo bloqueante (espera resposta)

        # 2. Monta o comando de solicitação (Baseado no Wireshark: 20 01)
        # Estrutura: [20, 01, 00, 00]
        comando = [0x00] * 32
        comando[0] = 0x20  # Byte 0: Header
        comando[1] = 0x01  # Byte 1: Solicitar Status
        
        # Calcula o checksum dos 31 bytes de dados
        # (Nota: comando[0:31] pega do índice 0 ao 30)
        checksum = calcular_checksum(comando[0:31])
        comando[31] = checksum

        # 3. Envia o comando
        device.write([0x00] + comando)
        
        # 4. Lê a resposta (32 bytes)
        # Lemos 64 bytes para garantir, pois alguns drivers retornam headers extras
        resposta = device.read(64, timeout_ms=2000)

        if resposta:
            # Procura pelo padrão de resposta. 
            # O nível é o quarto byte dessa sequência.
            
            # Vamos converter para lista para facilitar a busca
            lista_resp = list(resposta)
            
            # Tenta achar onde começa o cabeçalho 0x20
            try:
                idx_header = lista_resp.index(0x20)
                
                # O formato é: 20 01 00 [BATERIA]
                idx_bateria = idx_header + 3
                
                if idx_bateria < len(lista_resp):
                    nivel = lista_resp[idx_bateria]
                    print(f"\n>>> Nível da Bateria: {nivel}% <<<\n")
                    return nivel 
                else:
                    print("Pacote incompleto recebido.")
                    
            except ValueError:
                print("Resposta recebida, mas não contem o cabeçalho 0x20 esperado.")
                print(f"Hex Dump: {[hex(x) for x in lista_resp]}")

        else:
            print("Nenhuma resposta recebida (Timeout).")

        device.close()

    except Exception as e:
        print(f"Erro: {e}")
    
def loop_icone(icon):
    """
    Loop para atualizar o ícone da bateria periodicamente.
    """
    global ultimo_nivel_bateria
    while True:
        nivel = obter_nivel_bateria()
        if nivel is not None:
            ultimo_nivel_bateria = f"{nivel}%"
            # Define a cor do ícone baseado no nível da bateria
            if nivel >= 75:
                cor_fundo = (0, 128, 0, 255)  # Verde
            elif nivel >= 40:
                cor_fundo = (255, 165, 0, 255)  # Laranja
            else:
                cor_fundo = (255, 0, 0, 255)  # Vermelho
            
            imagem = criar_imagem_icone(ultimo_nivel_bateria, cor_fundo)
            icon.icon = imagem
            icon.title = f"Nível da Bateria: {ultimo_nivel_bateria}"
        else:
            ultimo_nivel_bateria = "--"
            imagem = criar_imagem_icone(ultimo_nivel_bateria, (128, 128, 128, 255))  # Cinza
            icon.icon = imagem
            icon.title = "Nível da Bateria: Desconhecido"
        
        time.sleep(INTERVALO_ATUALIZACAO)
def sair_app (icon, item):
    icon.stop()

def main():
    # Nosso menu para clicar com o botão direito
    menu= Menu(
        MenuItem('Sair', sair_app)
    )
    #cria o ícone inicial
    imagem_inicial = criar_imagem_icone("--", (128, 128, 128, 255))  # Cinza

    global icon_app
    icon_app = Icon("Bateria Teclado", imagem_inicial, "Nível da Bateria: --", menu)

    # Inicia a thread de atualização USB para não travar o ícone)
    thread_icone = threading.Thread(target=loop_icone, args=(icon_app,), daemon=True)
    thread_icone.start()

        # Inicia o ícone na tray
    icon_app.run()
    # Nosso menu para clicar com o botão direito

if __name__ == "__main__":
    main()