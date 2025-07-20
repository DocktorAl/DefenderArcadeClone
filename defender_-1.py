import pygame
import random
import sys
import math
import numpy as np # Import numpy for sound array

# --- Initialization ---
pygame.init()
pygame.mixer.init() # For sounds

# --- Screen and World Variables ---
SCREEN_WIDTH = 800
SCREEN_HEIGHT = 600
screen = pygame.display.set_mode((SCREEN_WIDTH, SCREEN_HEIGHT))
pygame.display.set_caption("Defender")

# The game world is wider than the screen to allow for scrolling
WORLD_WIDTH = SCREEN_WIDTH * 4

# --- Game Clock ---
clock = pygame.time.Clock()
FPS = 60

# --- Colors ---
WHITE = (255, 255, 255)
BLACK = (0, 0, 0)
RED = (255, 0, 0)
GREEN = (0, 255, 0)
BLUE = (0, 0, 255)
YELLOW = (255, 255, 0)
CYAN = (0, 255, 255)

# --- Fonts ---
font = pygame.font.SysFont("Consolas", 18, bold=True)

# --- Sound Effects (simple synthesized sounds) ---
def create_sound(freq, duration_ms):
    """ Creates a synthesized sound using numpy arrays. """
    sample_rate = pygame.mixer.get_init()[0]
    # Use the bit-size of the mixer to calculate the max amplitude.
    max_amp = 2**(abs(pygame.mixer.get_init()[1]) - 1) - 1
    duration_samples = int(duration_ms * sample_rate / 1000)
    
    # Create the numpy array for the sound samples
    samples = [max_amp * math.sin(2 * math.pi * freq * i / sample_rate) for i in range(duration_samples)]
    mono_array = np.array(samples, dtype=np.int16)
    
    # Convert mono array to a 2D stereo array
    stereo_array = np.column_stack([mono_array, mono_array])
    
    # Create the sound from the numpy array
    sound = pygame.sndarray.make_sound(stereo_array)
    sound.set_volume(0.1)
    return sound

laser_sound = create_sound(440, 100)
explosion_sound = create_sound(220, 400)
rescue_sound = create_sound(880, 200)

# --- Game Classes ---

class Player(pygame.sprite.Sprite):
    """ The player's spaceship. """
    def __init__(self):
        super().__init__()
        self.image = pygame.Surface((40, 20), pygame.SRCALPHA)
        pygame.draw.polygon(self.image, YELLOW, [(0, 10), (10, 0), (40, 10), (10, 20)])
        self.rect = self.image.get_rect(center=(SCREEN_WIDTH / 2, SCREEN_HEIGHT / 2))
        self.world_x = WORLD_WIDTH / 2
        self.world_y = SCREEN_HEIGHT / 2
        self.speed_x = 0
        self.speed_y = 0
        self.lives = 3
        self.bombs = 3

    def update(self):
        # Handle movement from keyboard input
        self.speed_x = 0
        self.speed_y = 0
        keys = pygame.key.get_pressed()
        if keys[pygame.K_LEFT] or keys[pygame.K_a]:
            self.speed_x = -6
        if keys[pygame.K_RIGHT] or keys[pygame.K_d]:
            self.speed_x = 6
        if keys[pygame.K_UP] or keys[pygame.K_w]:
            self.speed_y = -6
        if keys[pygame.K_DOWN] or keys[pygame.K_s]:
            self.speed_y = 6

        # Update world position
        self.world_x += self.speed_x
        self.world_y += self.speed_y

        # World wrapping
        if self.world_x < 0:
            self.world_x = WORLD_WIDTH
        if self.world_x > WORLD_WIDTH:
            self.world_x = 0
            
        # Screen boundaries for Y-axis
        if self.world_y < 50: # Don't go into scanner area
            self.world_y = 50
        if self.world_y > SCREEN_HEIGHT - 70: # Don't go into terrain
            self.world_y = SCREEN_HEIGHT - 70

        self.rect.centery = self.world_y

    def shoot(self):
        laser = Laser(self.world_x, self.rect.centery)
        all_sprites.add(laser)
        lasers.add(laser)
        laser_sound.play()

class Laser(pygame.sprite.Sprite):
    """ A laser beam fired by the player. """
    def __init__(self, x, y):
        super().__init__()
        self.image = pygame.Surface((15, 3))
        self.image.fill(CYAN)
        self.rect = self.image.get_rect(center=(x, y))
        self.world_x = x
        self.world_y = y # FIX: Added missing world_y attribute
        self.speed_x = 20

    def update(self):
        self.world_x += self.speed_x
        # Remove laser if it goes far off-screen
        if self.world_x > camera_x + SCREEN_WIDTH + 200 or self.world_x < camera_x - 200:
            self.kill()

class Lander(pygame.sprite.Sprite):
    """ An alien that abducts humanoids. """
    def __init__(self):
        super().__init__()
        self.image = pygame.Surface((20, 20), pygame.SRCALPHA)
        pygame.draw.polygon(self.image, GREEN, [(0,0), (20,0), (15,20), (5,20)])
        self.rect = self.image.get_rect()
        self.world_x = random.randint(0, WORLD_WIDTH)
        self.world_y = random.randint(50, 150)
        self.speed_y = 1
        self.target_humanoid = None
        self.has_humanoid = False

    def update(self):
        if self.has_humanoid:
            # Fly upwards with the humanoid
            self.world_y -= self.speed_y
            self.target_humanoid.world_y = self.world_y + 20
            if self.world_y < 0: # Reached top, becomes a mutant (simplified)
                self.kill()
                self.target_humanoid.kill()
        elif self.target_humanoid:
            # Move towards the target humanoid
            if self.world_x < self.target_humanoid.world_x:
                self.world_x += 1
            else:
                self.world_x -= 1
            if self.world_y < self.target_humanoid.world_y:
                self.world_y += self.speed_y
            # Check for grab
            if abs(self.world_x - self.target_humanoid.world_x) < 10 and \
               abs(self.world_y - self.target_humanoid.world_y) < 10:
                self.has_humanoid = True
                self.target_humanoid.is_abducted = True
        else:
            # Find a humanoid to abduct
            if len(humanoids) > 0:
                # Ensure the humanoid is not already targeted
                available_humanoids = [h for h in humanoids.sprites() if not h.is_abducted and not h.is_falling]
                if available_humanoids:
                    self.target_humanoid = random.choice(available_humanoids)
            self.world_y += self.speed_y
            if self.world_y > SCREEN_HEIGHT - 80:
                self.speed_y = 0 # Hover above ground

class Humanoid(pygame.sprite.Sprite):
    """ A person to be defended on the planet surface. """
    def __init__(self):
        super().__init__()
        self.image = pygame.Surface((10, 15))
        self.image.fill(WHITE)
        self.rect = self.image.get_rect()
        self.world_x = random.randint(0, WORLD_WIDTH)
        self.world_y = SCREEN_HEIGHT - 65
        self.is_abducted = False
        self.is_falling = False

    def update(self):
        if self.is_falling:
            self.world_y += 3
            if self.world_y >= SCREEN_HEIGHT - 65:
                self.world_y = SCREEN_HEIGHT - 65
                self.is_falling = False
                self.is_abducted = False # Can be abducted again

# --- Helper Functions ---

def draw_terrain():
    """ Draws the mountainous terrain at the bottom. """
    for i in range(len(terrain_points) - 1):
        p1_world = terrain_points[i]
        p2_world = terrain_points[i+1]
        p1_screen = (p1_world[0] - camera_x, p1_world[1])
        p2_screen = (p2_world[0] - camera_x, p2_world[1])
        pygame.draw.line(screen, GREEN, p1_screen, p2_screen, 2)

def draw_scanner():
    """ Draws the mini-map at the top. """
    pygame.draw.rect(screen, BLACK, (0, 0, SCREEN_WIDTH, 40))
    pygame.draw.rect(screen, WHITE, (0, 0, SCREEN_WIDTH, 40), 1)
    # Draw enemies
    for enemy in enemies:
        scan_x = int(enemy.world_x * SCREEN_WIDTH / WORLD_WIDTH)
        pygame.draw.rect(screen, RED, (scan_x, 10, 2, 2))
    # Draw humanoids
    for h in humanoids:
        scan_x = int(h.world_x * SCREEN_WIDTH / WORLD_WIDTH)
        pygame.draw.rect(screen, GREEN, (scan_x, 30, 2, 2))
    # Draw player
    scan_x = int(player.world_x * SCREEN_WIDTH / WORLD_WIDTH)
    pygame.draw.rect(screen, YELLOW, (scan_x-2, 20, 4, 4))

def draw_text(text, x, y):
    """ Renders and draws text to the screen. """
    text_surface = font.render(text, True, WHITE)
    screen.blit(text_surface, (x, y))

# --- Game Setup ---
all_sprites = pygame.sprite.Group()
enemies = pygame.sprite.Group()
lasers = pygame.sprite.Group()
humanoids = pygame.sprite.Group()

player = Player()
all_sprites.add(player)

for _ in range(10):
    h = Humanoid()
    all_sprites.add(h)
    humanoids.add(h)

for _ in range(8):
    e = Lander()
    all_sprites.add(e)
    enemies.add(e)

# Generate terrain points
terrain_points = []
for x in range(0, WORLD_WIDTH + 1, 40):
    y = SCREEN_HEIGHT - 50 + random.randint(-10, 10)
    terrain_points.append((x, y))

camera_x = player.world_x - SCREEN_WIDTH / 2
score = 0

# --- Main Game Loop ---
running = True
game_over = False
while running:
    # --- Event Handling ---
    for event in pygame.event.get():
        if event.type == pygame.QUIT:
            running = False
        if event.type == pygame.KEYDOWN:
            if event.key == pygame.K_ESCAPE:
                running = False
            if event.key == pygame.K_SPACE:
                player.shoot()
            if event.key == pygame.K_b: # Smart Bomb
                if player.bombs > 0:
                    player.bombs -= 1
                    for enemy in list(enemies):
                        # Check if enemy is on screen
                        if camera_x < enemy.world_x < camera_x + SCREEN_WIDTH:
                            enemy.kill()
                            score += 100
                            explosion_sound.play()


    if game_over:
        # Game over logic here
        continue

    # --- Update ---
    all_sprites.update()
    camera_x = player.world_x - SCREEN_WIDTH / 2

    # Laser hits Lander
    hits = pygame.sprite.groupcollide(enemies, lasers, True, True)
    for hit in hits:
        score += 150
        explosion_sound.play()
        # If lander had a humanoid, it starts falling
        if hit.has_humanoid:
            hit.target_humanoid.is_abducted = False
            hit.target_humanoid.is_falling = True

    # Player hits Lander
    hits = pygame.sprite.spritecollide(player, enemies, True)
    if hits:
        player.lives -= 1
        explosion_sound.play()
        if player.lives <= 0:
            game_over = True # Placeholder for game over sequence
    
    # Player rescues falling humanoid
    rescued = pygame.sprite.spritecollide(player, humanoids, False)
    for h in rescued:
        if h.is_falling:
            h.is_falling = False
            score += 500
            rescue_sound.play()


    # --- Drawing ---
    screen.fill(BLACK) # Starry sky

    # Update sprite screen positions based on camera
    for sprite in all_sprites:
        sprite.rect.centerx = int(sprite.world_x - camera_x)
        sprite.rect.centery = int(sprite.world_y)

    all_sprites.draw(screen)
    draw_terrain()
    draw_scanner()

    # Draw UI
    draw_text(f"SCORE: {score}", 10, 45)
    draw_text(f"LIVES: {player.lives}", 200, 45)
    draw_text(f"BOMBS: {player.bombs}", 350, 45)


    # --- Update Display ---
    pygame.display.flip()
    clock.tick(FPS)

# --- Quit Pygame ---
pygame.quit()
sys.exit()