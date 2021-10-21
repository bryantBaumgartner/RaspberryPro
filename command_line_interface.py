import inspect
import logging
import shlex
import asyncio

from aioconsole import ainput
from evdev import InputDevice, categorize, ecodes

from joycontrol.controller_state import ControllerState, button_press, button_release, StickState
from joycontrol.transport import NotConnectedError

logger = logging.getLogger(__name__)
dev = InputDevice('/dev/input/event1')

def _print_doc(string):
    """
    Attempts to remove common white space at the start of the lines in a doc string
    to unify the output of doc strings with different indention levels.

    Keeps whitespace lines intact.

    :param fun: function to print the doc string of
    """
    lines = string.split('\n')
    if lines:
        prefix_i = 0
        for i, line_0 in enumerate(lines):
            # find non empty start lines
            if line_0.strip():
                # traverse line and stop if character mismatch with other non empty lines
                for prefix_i, c in enumerate(line_0):
                    if not c.isspace():
                        break
                    if any(lines[j].strip() and (prefix_i >= len(lines[j]) or c != lines[j][prefix_i])
                           for j in range(i+1, len(lines))):
                        break
                break

        for line in lines:
            print(line[prefix_i:] if line.strip() else line)


class CLI:
    def __init__(self):
        self.commands = {}

    def add_command(self, name, command):
        if name in self.commands:
            raise ValueError(f'Command {name} already registered.')
        self.commands[name] = command

    async def cmd_help(self):
        print('Commands:')
        for name, fun in inspect.getmembers(self):
            if name.startswith('cmd_') and fun.__doc__:
                _print_doc(fun.__doc__)

        for name, fun in self.commands.items():
            if fun.__doc__:
                _print_doc(fun.__doc__)

        print('Commands can be chained using "&&"')
        print('Type "exit" to close.')


    #Custom Keyboard Input
    async def KeyCodeInput(self, controller_state: ControllerState, code, value):
        await controller_state.connect()
        
        #1-Press 0-Release 2-Hold
        if value == 1:
            if code == 36:#j
                await button_press(controller_state, 'a')
            if code == 37:#k
                await button_press(controller_state, 'b')
            if code == 23:#i
                await button_press(controller_state, 'x')
            if code == 38:#l
                await button_press(controller_state, 'y')
            if code == 22:#u
                await button_press(controller_state, 'l')
            if code == 24:#o
                await button_press(controller_state, 'r')
            if code == 20:#t
                await button_press(controller_state, 'plus')
            if code == 21:#y
                await button_press(controller_state, 'minus')
            if code == 25:#p
                await button_press(controller_state, 'home')
                
            #Stick Controls    
            if code == 17:
                controller_state.l_stick_state.set_up()
                await controller_state.send()
            if code == 30:
                controller_state.l_stick_state.set_left()
                await controller_state.send()
            if code == 31:
                controller_state.l_stick_state.set_down()
                await controller_state.send()
            if code == 32:
                controller_state.l_stick_state.set_right()
                await controller_state.send()
                
        if value == 0:
            if code == 36:#j
                await button_release(controller_state, 'a')
            if code == 37:#k
                await button_release(controller_state, 'b')
            if code == 23:#i
                await button_release(controller_state, 'x')
            if code == 38:#l
                await button_release(controller_state, 'y')
            if code == 22:#u
                await button_release(controller_state, 'l')
            if code == 24:#o
                await button_release(controller_state, 'r')
            if code == 20:#t
                await button_release(controller_state, 'plus')
            if code == 21:#y
                await button_release(controller_state, 'minus')
            if code == 25:#p
                await button_release(controller_state, 'home')
            
            #Stick Controls    
            if code == 17:
                controller_state.l_stick_state.release_vertical()
                await controller_state.send()
            if code == 30:
                controller_state.l_stick_state.release_horizontal()
                await controller_state.send()
            if code == 31:
                controller_state.l_stick_state.release_vertical()
                await controller_state.send()
            if code == 32:
                controller_state.l_stick_state.release_horizontal()
                await controller_state.send()
            
    async def run(self):
        while True:
            user_input = await ainput(prompt='cmd >> ')
            if not user_input:
                continue

            for command in user_input.split('&&'):
                cmd, *args = shlex.split(command)

                if cmd == 'exit':
                    return

                if hasattr(self, f'cmd_{cmd}'):
                    try:
                        result = await getattr(self, f'cmd_{cmd}')(*args)
                        if result:
                            print(result)
                    except Exception as e:
                        print(e)
                elif cmd in self.commands:
                    try:
                        result = await self.commands[cmd](*args)
                        if result:
                            print(result)
                    except Exception as e:
                        print(e)
                else:
                    print('command', cmd, 'not found, call help for help.')

    @staticmethod
    def deprecated(message):
        async def dep_printer(*args, **kwargs):
            print(message)

        return dep_printer


class ControllerCLI(CLI):
    def __init__(self, controller_state: ControllerState):
        super().__init__()
        self.controller_state = controller_state

    async def cmd_help(self):
        print('Button commands:')
        print(', '.join(self.controller_state.button_state.get_available_buttons()))
        print()
        await super().cmd_help()

    @staticmethod
    def _set_stick(stick, direction, value):
        if direction == 'center':
            stick.set_center()
        elif direction == 'up':
            stick.set_up()
        elif direction == 'down':
            stick.set_down()
        elif direction == 'left':
            stick.set_left()
        elif direction == 'right':
            stick.set_right()
        elif direction in ('h', 'horizontal'):
            if value is None:
                raise ValueError(f'Missing value')
            try:
                val = int(value)
            except ValueError:
                raise ValueError(f'Unexpected stick value "{value}"')
            stick.set_h(val)
        elif direction in ('v', 'vertical'):
            if value is None:
                raise ValueError(f'Missing value')
            try:
                val = int(value)
            except ValueError:
                raise ValueError(f'Unexpected stick value "{value}"')
            stick.set_v(val)
        else:
            raise ValueError(f'Unexpected argument "{direction}"')

        return f'{stick.__class__.__name__} was set to ({stick.get_h()}, {stick.get_v()}).'

    async def cmd_stick(self, side, direction, value=None):
        """
        stick - Command to set stick positions.
        :param side: 'l', 'left' for left control stick; 'r', 'right' for right control stick
        :param direction: 'center', 'up', 'down', 'left', 'right';
                          'h', 'horizontal' or 'v', 'vertical' to set the value directly to the "value" argument
        :param value: horizontal or vertical value
        """
        if side in ('l', 'left'):
            stick = self.controller_state.l_stick_state
            return ControllerCLI._set_stick(stick, direction, value)
        elif side in ('r', 'right'):
            stick = self.controller_state.r_stick_state
            return ControllerCLI._set_stick(stick, direction, value)
        else:
            raise ValueError('Value of side must be "l", "left" or "r", "right"')

    async def run(self):
        await self.controller_state.connect()
        print(dev)
        
        while True:
            for event in dev.read_loop():
                if event.type == ecodes.EV_KEY:
                    await self.KeyCodeInput(self.controller_state, event.code, event.value);            
                    
            try:
                await self.controller_state.send()
            except NotConnectedError:
                logger.info('Connection was lost.')
                return
